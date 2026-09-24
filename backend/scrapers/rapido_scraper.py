"""
rapido_scraper.py
─────────────────
Scrapes fare estimates from rapido.bike (Rapido's web platform).

Rapido offers bike taxis, autos, and cabs — we fetch the cheapest available.

Strategy:
  1. Load cookies if saved → check login
  2. Phone-based OTP login (Rapido doesn't support password login)
  3. Enter route → parse fare results
"""

import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from scrapers.base_scraper import BaseScraper


class RapidoSelectors:
    BASE_URL        = "https://rapido.bike"
    BOOKING_URL     = "https://rapido.bike"
    SEARCH_BTN      = "button.jsx-857791620, button[class*='BookRide'], button.search-btn, button[type='submit']"

    # Login
    PHONE_INPUT     = 'input[type="tel"], input[placeholder*="mobile"], input[placeholder*="phone"]'
    SEND_OTP_BTN    = 'button[type="submit"], .send-otp-btn, button[class*="otp"]'
    OTP_INPUT       = 'input[type="tel"][maxlength="6"], input[placeholder*="OTP"], input[placeholder*="otp"]'
    VERIFY_BTN      = 'button[type="submit"], .verify-btn'

    # Booking
    PICKUP_INPUT    = 'input[placeholder*="Pickup"], input[placeholder*="pickup"], #pickup'
    DEST_INPUT      = 'input[placeholder*="Drop"], input[placeholder*="drop"], input[placeholder*="destination"], #destination'
    SUGGESTION      = '[class*="suggestion"], [class*="autocomplete"] li, .pac-item'

    # Fare cards
    RIDE_CARD       = '[class*="rideCard"], [class*="vehicle-card"], [class*="ride-option"], .ride-type-card'
    RIDE_PRICE      = '[class*="price"], [class*="fare"], .price-text, .fare-amount'
    RIDE_ETA        = '[class*="eta"], [class*="time"], .eta-text'
    RIDE_NAME       = '[class*="name"], [class*="title"], h3, h4, .vehicle-name'

    LOGGED_IN_CHECK = '.user-profile, [class*="profile"], .logout, [class*="loggedIn"]'


class RapidoScraper(BaseScraper):

    @property
    def platform_name(self) -> str:
        return "Rapido"

    def login(self) -> bool:
        if not self.driver:
            self.start_driver()

        if self.cookies_exist():
            self.logger.info("Trying saved Rapido cookies...")
            self.load_cookies(RapidoSelectors.BASE_URL)
            if self._is_logged_in():
                self.logger.info("✅ Rapido cookie login successful!")
                return True

        phone = os.getenv("RAPIDO_PHONE", "")

        return self._credential_login(phone)

    def _is_logged_in(self) -> bool:
        try:
            self.driver.get(RapidoSelectors.BASE_URL)
            self._human_delay(2, 3)
            login_fields = self.driver.find_elements(
                By.CSS_SELECTOR, f"{RapidoSelectors.PHONE_INPUT}, {RapidoSelectors.OTP_INPUT}"
            )
            visible_login = [el for el in login_fields if el.is_displayed()]
            if visible_login:
                return False
            pickup = self.driver.find_elements(By.CSS_SELECTOR, RapidoSelectors.PICKUP_INPUT)
            return bool(pickup)
        except Exception as exc:
            self.logger.warning("Rapido login check failed: %s", exc)
            return False

    def _credential_login(self, phone: str) -> bool:
        try:
            self.driver.get(RapidoSelectors.BASE_URL)
            self._human_delay(2, 3)

            # Rapido login requires typing something into pickup to trigger login modal
            # or clicking a login button if available.
            # The prompt is a modal popup.

            self.logger.warning(
                "Please complete Rapido login manually in the browser. You have 120s..."
            )
            for _ in range(120):
                time.sleep(1)
                try:
                    login_fields = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        f"{RapidoSelectors.PHONE_INPUT}, {RapidoSelectors.OTP_INPUT}",
                    )
                    visible_login = [el for el in login_fields if el.is_displayed()]
                    pickup = self.driver.find_elements(
                        By.CSS_SELECTOR, RapidoSelectors.PICKUP_INPUT
                    )
                    if pickup and not visible_login:
                        self.save_cookies()
                        self.logger.info("Rapido login successful.")
                        return True
                except Exception:
                    pass

            if self._is_logged_in():
                self.save_cookies()
                self.logger.info("Rapido login successful.")
                return True

            self.logger.error("Rapido login timed out — cookies not saved.")
            return False

        except Exception as e:
            self.logger.error(f"Rapido login error: {e}")
            self._take_screenshot("rapido_login_error")
            return False

    def get_fare(self, pickup: str, destination: str) -> dict:
        if not self.driver:
            self.start_driver()

        try:
            # Try the booking page directly
            self.driver.get(RapidoSelectors.BOOKING_URL)
            self._human_delay(2, 3)

            # Enter pickup
            pickup_field = self._wait_for(By.CSS_SELECTOR, RapidoSelectors.PICKUP_INPUT)
            pickup_field.click()
            self._type_slowly(pickup_field, pickup)
            self._human_delay(2, 3)

            try:
                suggestions = self.driver.find_elements(By.CSS_SELECTOR, ".dropdown-item")
                if suggestions:
                    self.driver.execute_script("arguments[0].click();", suggestions[0])
                else:
                    pickup_field.send_keys(Keys.ARROW_DOWN)
                    pickup_field.send_keys(Keys.ENTER)
                    self._human_delay(1, 1)
                    # Try to close any dropdown overlay
                    self.driver.execute_script("document.body.click();")
            except Exception:
                pickup_field.send_keys(Keys.ARROW_DOWN)
                pickup_field.send_keys(Keys.ENTER)
                self.driver.execute_script("document.body.click();")
                
            self._human_delay(1, 2)

            # Enter destination
            dest_field = self._wait_for(By.CSS_SELECTOR, RapidoSelectors.DEST_INPUT)
            # Use JS click to bypass any overlapping dropdowns
            self.driver.execute_script("arguments[0].click();", dest_field)
            self._type_slowly(dest_field, destination)
            self._human_delay(2, 3)

            try:
                suggestions = self.driver.find_elements(By.CSS_SELECTOR, ".dropdown-item")
                if suggestions:
                    self.driver.execute_script("arguments[0].click();", suggestions[0])
                else:
                    dest_field.send_keys(Keys.ARROW_DOWN)
                    dest_field.send_keys(Keys.ENTER)
            except Exception:
                dest_field.send_keys(Keys.ARROW_DOWN)
                dest_field.send_keys(Keys.ENTER)

            self._human_delay(2, 3)
            
            # Try to click search/book button if it exists
            try:
                btn = self.driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'book ride') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search')]")
                if btn:
                    btn[0].click()
                else:
                    # Fallback to CSS selector
                    self._click(By.CSS_SELECTOR, RapidoSelectors.SEARCH_BTN, timeout=5)
            except Exception as e:
                self.logger.debug(f"Could not click Rapido search button: {e}")

            self._human_delay(4, 6)
            return self._parse_fares()

        except TimeoutException:
            self._take_screenshot("rapido_fare_timeout")
            return self._build_error_result("Timeout waiting for Rapido fares")
        except Exception as e:
            self._take_screenshot("rapido_fare_error")
            return self._build_error_result(str(e))

    def _parse_fares(self) -> dict:
        soup = self._get_page_soup()
        cards = soup.select(RapidoSelectors.RIDE_CARD)

        if not cards:
            return self._fallback_parse(soup)

        best_fare = None
        best_min = float("inf")

        for card in cards:
            try:
                price_el = card.select_one(RapidoSelectors.RIDE_PRICE)
                eta_el   = card.select_one(RapidoSelectors.RIDE_ETA)
                name_el  = card.select_one(RapidoSelectors.RIDE_NAME)

                price_text = price_el.get_text(strip=True) if price_el else ""
                eta_text   = eta_el.get_text(strip=True)   if eta_el   else "N/A"
                name_text  = name_el.get_text(strip=True)  if name_el  else "Rapido Bike"

                if not price_text:
                    continue

                fare_min, fare_max = self._parse_fare_range(price_text)
                if fare_min < best_min and fare_min > 0:
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
                self.logger.debug(f"Rapido card parse error: {e}")

        if best_fare:
            return best_fare
        return self._fallback_parse(soup)

    def _fallback_parse(self, soup) -> dict:
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
                "ride_type": "Rapido Bike",
                "status":    "success",
                "error_msg": "(fallback parser)",
            }
        return self._build_error_result("No Rapido fare data found")
