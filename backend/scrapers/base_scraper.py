"""
base_scraper.py
───────────────
Base class for all cab scrapers.
Handles: Chrome setup, anti-bot evasion, cookie load/save, waits.
All platform-specific scrapers inherit from this.
"""

import os
import time
import pickle
import random
import logging
from pathlib import Path
from abc import ABC, abstractmethod

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from utils.config import COOKIES_DIR, LOGS_DIR
from utils.logging_config import setup_logging
from utils.storage import utc_now_iso

load_dotenv()
setup_logging()

COOKIES_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class BaseScraper(ABC):
    """
    Abstract base class for Uber, Ola, Rapido scrapers.

    Subclasses must implement:
        - login()
        - get_fare(pickup, destination) -> dict
        - platform_name (property)
    """

    def __init__(self, headless: bool = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.headless = headless if headless is not None else (
            os.getenv("HEADLESS", "False").lower() == "true"
        )
        self.driver: webdriver.Chrome | None = None
        self.wait: WebDriverWait | None = None

    # ── Abstract interface ─────────────────────────────────────────────────────

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """e.g. 'Uber', 'Ola', 'Rapido'"""

    @abstractmethod
    def login(self) -> bool:
        """Perform login. Returns True on success."""

    @abstractmethod
    def get_fare(self, pickup: str, destination: str) -> dict:
        """
        Scrape fare for the given route.

        Returns dict like:
        {
            "platform":    "Uber",
            "fare":        "₹120–₹140",
            "fare_min":    120,
            "fare_max":    140,
            "eta":         "8 min",
            "ride_type":   "UberGo",
            "status":      "success" | "error" | "login_required",
            "error_msg":   ""
        }
        """

    # ── Chrome setup ───────────────────────────────────────────────────────────

    @staticmethod
    def _get_chromedriver_path() -> str:
        """
        Resolve the correct win64 chromedriver.exe path.
        Prefers the manually-downloaded win64 binary in the WDM cache,
        then falls back to letting WDM resolve (which may still pick win32).
        """
        import glob
        wdm_root = Path.home() / ".wdm" / "drivers" / "chromedriver" / "win64"
        # Look for any chromedriver-win64 folder (newest version first)
        pattern = str(wdm_root / "**" / "chromedriver-win64" / "chromedriver.exe")
        matches = sorted(glob.glob(pattern, recursive=True), reverse=True)
        if matches:
            return matches[0]  # newest cached win64 binary
        # Fall back to WDM (may download)
        return ChromeDriverManager().install()

    def start_driver(self):
        """Initialize Chrome with anti-detection settings."""
        self.logger.info(f"Starting Chrome for {self.platform_name}...")
        options = Options()

        if self.headless:
            options.add_argument("--headless=new")  # New headless mode (Chrome 112+)

        # ── Anti-bot / stealth settings ────────────────────────────────────────
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1366,768")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        )

        driver_path = self._get_chromedriver_path()
        self.logger.info(f"Using chromedriver: {driver_path}")
        service = Service(driver_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, timeout=20)

        # Remove webdriver navigator property (key anti-bot trick)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        self.logger.info(f"Chrome ready for {self.platform_name}")

    def quit_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logger.info(f"Chrome closed for {self.platform_name}")

    # ── Cookie management ──────────────────────────────────────────────────────

    @property
    def cookie_path(self) -> Path:
        return COOKIES_DIR / f"{self.platform_name.lower()}_cookies.pkl"

    def save_cookies(self):
        """Save current browser cookies to disk."""
        if not self.driver:
            self.logger.warning("No driver active — cannot save cookies.")
            return False
        cookies = self.driver.get_cookies()
        with open(self.cookie_path, "wb") as f:
            pickle.dump(cookies, f)
        self.logger.info(f"✅ Saved {len(cookies)} cookies for {self.platform_name}")
        return True

    def load_cookies(self, base_url: str) -> bool:
        """
        Load saved cookies into the browser.
        Must navigate to base_url first so cookies match the domain.
        """
        if not self.cookie_path.exists():
            self.logger.warning(f"No saved cookies for {self.platform_name}")
            return False

        self.driver.get(base_url)
        self._human_delay(1, 2)

        with open(self.cookie_path, "rb") as f:
            cookies = pickle.load(f)

        for cookie in cookies:
            # Selenium sometimes chokes on 'sameSite' values — strip it safely
            cookie.pop("sameSite", None)
            try:
                self.driver.add_cookie(cookie)
            except Exception as e:
                self.logger.debug(f"Skipped cookie: {e}")

        self.driver.refresh()
        self._human_delay(2, 3)
        self.logger.info(f"🍪 Loaded cookies for {self.platform_name}")
        return True

    def cookies_exist(self) -> bool:
        return self.cookie_path.exists()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Random delay to mimic human behaviour and avoid bot detection."""
        time.sleep(random.uniform(min_sec, max_sec))

    def _wait_for(self, by: By, selector: str, timeout: int = 20):
        """Wait until element is visible and return it."""
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by, selector))
        )

    def _click(self, by: By, selector: str, timeout: int = 20):
        """Wait for element then click it safely."""
        el = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        self._human_delay(0.3, 0.8)
        el.click()
        return el

    def _type_slowly(self, element, text: str):
        """Type text character by character like a human."""
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))

    def _get_page_soup(self) -> BeautifulSoup:
        """Return BeautifulSoup of current page source."""
        return BeautifulSoup(self.driver.page_source, "html.parser")

    def _scroll_to(self, element):
        """Scroll element into view."""
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        self._human_delay(0.3, 0.6)

    def _take_screenshot(self, name: str = "debug"):
        """Save a debug screenshot into the project logs folder."""
        path = LOGS_DIR / f"{self.platform_name}_{name}.png"
        try:
            self.driver.save_screenshot(str(path))
            self.logger.info(f"Screenshot saved: {path}")
        except Exception as exc:
            self.logger.warning("Could not save screenshot: %s", exc)

    @staticmethod
    def _parse_fare_range(fare_text: str) -> tuple[int, int]:
        """
        Parse fare strings like '₹120–₹140', '₹85', 'Rs. 200-250'
        Returns (min_fare, max_fare) as integers.
        """
        import re
        numbers = re.findall(r"\d+", fare_text.replace(",", ""))
        if not numbers:
            return 0, 0
        nums = [int(n) for n in numbers]
        return min(nums), max(nums)

    def _build_error_result(self, msg: str) -> dict:
        self.logger.error("%s: %s", self.platform_name, msg)
        return {
            "platform": self.platform_name,
            "fare": "N/A",
            "fare_min": 0,
            "fare_max": 0,
            "eta": "N/A",
            "ride_type": "N/A",
            "status": "error",
            "error_msg": msg,
            "scraped_at": utc_now_iso(),
            "duration_ms": 0,
        }
