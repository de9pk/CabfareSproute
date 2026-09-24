"""
uber_scraper.py
───────────────
Scrapes fare estimates from m.uber.com (mobile web — simpler DOM than app).

Strategy:
  1. Try loading saved cookies → check if already logged in
  2. If not logged in → use env vars to log in via OTP flow
  3. Input pickup + destination → extract fare card data
  4. Parse fare range & ETA → return structured result

NOTE: Uber's DOM changes frequently. Selectors are as of early 2024.
      If scraping fails, enable headless=False to watch what's happening,
      then update the XPath/CSS selectors below.
"""

import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scrapers.base_scraper import BaseScraper


# ── Selectors (update these if Uber changes their HTML) ────────────────────────
class UberSelectors:
    BASE_URL         = "https://m.uber.com"
    LOGIN_URL        = "https://m.uber.com/go/login"

    # Login page
    PHONE_INPUT      = '#PHONE_NUMBER_or_EMAIL_ADDRESS'
    NEXT_BTN         = 'button[data-testid="forward-button"]'
    OTP_INPUT        = 'input[name="verificationCode"]'
    PASSWORD_INPUT   = 'input[name="password"]'

    # Home / ride booking
    # Uber changed UI: inputs are on the home page directly.
    PICKUP_INPUT     = 'input[aria-label="Search for a location"]'
    DEST_INPUT       = 'input[aria-label="Search for a location"]'
    SEARCH_BTN       = 'button[aria-label="Search"]'

    # Fare results
    FARE_CARD        = '[data-testid="product-selector-card"]'
    FARE_PRICE       = '[data-testid="price-badge"]'
    FARE_ETA         = '[data-testid="product-time"]'
    FARE_NAME        = '[data-testid="product-name"]'

    # Logged-in check
    LOGGED_IN_CHECK  = 'input[aria-label="Search for a location"]'


class UberScraper(BaseScraper):

    @property
    def platform_name(self) -> str:
        return "Uber"

    # ── Login ──────────────────────────────────────────────────────────────────

    def login(self) -> bool:
        """
        Attempt login using:
          1. Saved cookies (preferred)
          2. Env var credentials (phone/password)
        Returns True if logged in successfully.
        """
        if not self.driver:
            self.start_driver()

        # Try cookie login first
        if self.cookies_exist():
            self.logger.info("Found saved cookies — attempting cookie login...")
            self.load_cookies(UberSelectors.BASE_URL)
            if self._is_logged_in():
                self.logger.info("✅ Cookie login successful!")
                return True
            self.logger.warning("Cookies expired — falling back to credential login")

        # Credential login
        phone = os.getenv("UBER_PHONE", "")
        password = os.getenv("UBER_PASSWORD", "")

        return self._credential_login(phone, password)

    def _is_logged_in(self) -> bool:
        try:
            self.driver.get(UberSelectors.BASE_URL)
            self._human_delay(2, 3)
            self.driver.find_element(By.CSS_SELECTOR, UberSelectors.LOGGED_IN_CHECK)
            return True
        except NoSuchElementException:
            return False

    def _credential_login(self, phone: str, password: str) -> bool:
        """Login with phone + password, or fully manual if no env vars."""
        try:
            self.driver.get(UberSelectors.LOGIN_URL)
            self._human_delay(2, 3)

            if phone:
                # Enter phone number
                phone_field = self._wait_for(By.CSS_SELECTOR, UberSelectors.PHONE_INPUT)
                self._type_slowly(phone_field, phone)
                self._human_delay(0.5, 1)

                # Click Next
                self._click(By.CSS_SELECTOR, UberSelectors.NEXT_BTN)
                self._human_delay(2, 3)

                # Try password field first
                try:
                    pwd_field = self._wait_for(By.CSS_SELECTOR, UberSelectors.PASSWORD_INPUT, timeout=5)
                    self._type_slowly(pwd_field, password)
                    self._click(By.CSS_SELECTOR, UberSelectors.NEXT_BTN)
                    self._human_delay(3, 5)
                except TimeoutException:
                    pass

            self.logger.warning(
                "⚠️  Please complete the login (phone/password/OTP) manually in the browser. "
                "You have 120 seconds..."
            )
            
            # Wait up to 120s for user to enter everything
            for _ in range(120):
                if self._is_logged_in():
                    self.save_cookies()
                    self.logger.info("✅ Credential login successful!")
                    return True
                time.sleep(1)

            self.logger.error("❌ Login failed or timed out.")
            return False

        except Exception as e:
            self.logger.error(f"Login error: {e}")
            self._take_screenshot("login_error")
            return False

    # ── Fare scraping ──────────────────────────────────────────────────────────

    # CSS selectors for autocomplete suggestions
    SUGGESTION_ITEM = 'li[data-baseweb="menu-item"]'
    # Destination input appears only after pickup is set
    DEST_INPUT_SELECTOR = 'input[aria-label="Dropoff location"], input[placeholder="Dropoff location"], input[aria-label="Search for a location"]'

    def get_fare(self, pickup: str, destination: str) -> dict:
        """
        Scrape Uber fare for pickup → destination.
        Uber mobile web shows fares without login.

        Flow:
          1. Page loads with single pickup input + suggestions list
          2. Type pickup → click first suggestion → page re-renders with destination input
          3. Type destination → click first suggestion → fare cards appear
          4. Parse cheapest fare
        """
        if not self.driver:
            self.start_driver()

        try:
            self.driver.get(UberSelectors.BASE_URL)
            self._human_delay(2, 4)

            # ── Step 1: Pickup ─────────────────────────────────────────────────
            self.logger.info("Waiting for pickup input...")
            self._wait_for(By.CSS_SELECTOR, UberSelectors.PICKUP_INPUT, timeout=15)
            self._safe_click_input(UberSelectors.PICKUP_INPUT)
            self._human_delay(0.8, 1.2)
            self._safe_type(UberSelectors.PICKUP_INPUT, pickup)
            self._human_delay(1.5, 2.5)

            self.logger.info("Selecting pickup suggestion...")
            if not self._click_first_suggestion(timeout=6):
                self.logger.debug("No pickup suggestion — using Enter fallback")
                self._safe_send_key(UberSelectors.PICKUP_INPUT, Keys.ENTER)
            self._human_delay(1.5, 2.5)

            # ── Step 2: Destination ────────────────────────────────────────────
            # After pickup is set, Uber shows a destination/dropoff input.
            self.logger.info("Waiting for destination input...")
            dest = self._resolve_dest_selector(timeout=8)
            if dest is None:
                self._take_screenshot("no_dest_input")
                return self._build_error_result("Destination input did not appear after setting pickup")

            dest_sel, dest_idx = dest
            self._safe_click_input(dest_sel, index=dest_idx)
            self._human_delay(0.8, 1.2)
            self._safe_type(dest_sel, destination, index=dest_idx)
            self._human_delay(1.5, 2.5)

            self.logger.info("Selecting destination suggestion...")
            if not self._click_first_suggestion(timeout=6):
                self.logger.debug("No destination suggestion — using Enter fallback")
                self._safe_send_key(dest_sel, Keys.ENTER, index=dest_idx)
            self._human_delay(3, 5)  # Wait for fare cards to render

            # ── Step 3: Parse fares ────────────────────────────────────────────
            self.logger.info("Parsing fare results...")
            return self._parse_fares()

        except TimeoutException:
            self._take_screenshot("fare_timeout")
            return self._build_error_result("Timeout waiting for Uber fare results")
        except Exception as e:
            self._take_screenshot("fare_error")
            return self._build_error_result(str(e))

    # ── Stale-element-safe helpers ─────────────────────────────────────────────

    def _safe_click_input(self, selector: str, index: int = 0):
        """Re-query and click an input by CSS selector (stale-safe)."""
        from selenium.common.exceptions import StaleElementReferenceException
        for attempt in range(3):
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if els and len(els) > index:
                    self.driver.execute_script("arguments[0].click();", els[index])
                    return
            except StaleElementReferenceException:
                self._human_delay(0.3, 0.5)
        self.logger.warning(f"Could not click input: {selector}[{index}]")

    def _safe_type(self, selector: str, text: str, index: int = 0):
        """Re-query input and type text char-by-char (stale-safe)."""
        from selenium.common.exceptions import StaleElementReferenceException
        import random, time
        for attempt in range(3):
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if els and len(els) > index:
                    el = els[index]
                    el.clear()
                    for char in text:
                        el.send_keys(char)
                        time.sleep(random.uniform(0.05, 0.12))
                    return
            except StaleElementReferenceException:
                self._human_delay(0.3, 0.5)
        self.logger.warning(f"Could not type into input: {selector}[{index}]")

    def _safe_send_key(self, selector: str, key, index: int = 0):
        """Re-query and send a key to an input (stale-safe)."""
        from selenium.common.exceptions import StaleElementReferenceException
        for attempt in range(3):
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if els and len(els) > index:
                    els[index].send_keys(key)
                    return
            except StaleElementReferenceException:
                self._human_delay(0.3, 0.5)

    def _resolve_dest_selector(self, timeout: int = 8) -> tuple[str, int] | None:
        """
        After pickup is set, detect which selector+index points to the destination input.
        Returns (css_selector, element_index) or None if not found within timeout.
        """
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Option A: dedicated dropoff / destination input
            dedicated = [
                'input[aria-label="Dropoff location"]',
                'input[placeholder="Dropoff location"]',
                'input[data-testid="location-typeahead-input-dropoff"]',
            ]
            for sel in dedicated:
                if self.driver.find_elements(By.CSS_SELECTOR, sel):
                    self.logger.debug(f"Dest input found via: {sel}")
                    return (sel, 0)
            # Option B: same selector as pickup, but 2nd element
            els = self.driver.find_elements(By.CSS_SELECTOR, UberSelectors.PICKUP_INPUT)
            if len(els) >= 2:
                self.logger.debug("Dest input is 2nd element of PICKUP_INPUT selector")
                return (UberSelectors.PICKUP_INPUT, 1)
            time.sleep(0.5)
        return None

    def _click_first_suggestion(self, timeout: int = 6) -> bool:
        """Wait for autocomplete suggestion list and click the first item."""
        try:
            suggestion = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.SUGGESTION_ITEM))
            )
            self._human_delay(0.3, 0.6)
            self.driver.execute_script("arguments[0].click();", suggestion)
            self.logger.debug("Clicked autocomplete suggestion")
            return True
        except TimeoutException:
            return False

    def _parse_fares(self) -> dict:
        """Extract the cheapest fare from Uber's product cards."""
        soup = self._get_page_soup()

        # Find all fare/product cards
        cards = soup.select(UberSelectors.FARE_CARD)

        if not cards:
            # Fallback: try reading any price text visible on page
            return self._fallback_parse(soup)

        best_fare = None
        best_min = float("inf")

        for card in cards:
            try:
                price_el = card.select_one(UberSelectors.FARE_PRICE)
                eta_el   = card.select_one(UberSelectors.FARE_ETA)
                name_el  = card.select_one(UberSelectors.FARE_NAME)

                price_text = price_el.get_text(strip=True) if price_el else ""
                eta_text   = eta_el.get_text(strip=True)   if eta_el   else "N/A"
                name_text  = name_el.get_text(strip=True)  if name_el  else "UberGo"

                if not price_text:
                    continue

                fare_min, fare_max = self._parse_fare_range(price_text)

                if fare_min < best_min:
                    best_min = fare_min
                    best_fare = {
                        "platform":  self.platform_name,
                        "fare":      price_text,
                        "fare_min":  fare_min,
                        "fare_max":  fare_max,
                        "eta":       eta_text,
                        "ride_type": name_text,
                        "status":    "success",
                        "error_msg": "",
                    }
            except Exception as e:
                self.logger.debug(f"Error parsing card: {e}")
                continue

        if best_fare:
            return best_fare

        return self._build_error_result("Could not parse any Uber fare cards")

    def _fallback_parse(self, soup) -> dict:
        """Fallback: search for any price-like text on the page."""
        import re
        text = soup.get_text()
        matches = re.findall(r"₹\s*\d+(?:[–\-]\d+)?", text)
        if matches:
            fare_text = matches[0]
            fare_min, fare_max = self._parse_fare_range(fare_text)
            return {
                "platform":  self.platform_name,
                "fare":      fare_text,
                "fare_min":  fare_min,
                "fare_max":  fare_max,
                "eta":       "N/A",
                "ride_type": "UberGo",
                "status":    "success",
                "error_msg": "(fallback parser used)",
            }
        return self._build_error_result("No fare data found on Uber page")
