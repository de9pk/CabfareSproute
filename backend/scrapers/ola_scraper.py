"""
ola_scraper.py
──────────────
Scrapes fare estimates from book.olacabs.com (Ola's web booking portal).

Strategy:
  1. Load cookies if available → check login state
  2. Credential login via phone/OTP or password
  3. Input pickup + destination → wait for fare results
  4. Parse all ride categories → return cheapest

NOTE: Ola heavily uses React — elements are dynamically rendered.
      Use explicit waits. If selectors break, inspect with F12 on book.olacabs.com.
"""

import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from scrapers.base_scraper import BaseScraper


class OlaSelectors:
    BASE_URL        = "https://book.olacabs.com"
    LOGIN_URL       = "https://book.olacabs.com"

    # Login
    LOGIN_BTN       = 'a[href*="login"], button[class*="login"], .login-btn'
    PHONE_INPUT     = 'input[type="tel"], input[name="mobile"], input[placeholder*="mobile"]'
    OTP_INPUT       = 'input[type="tel"][maxlength="6"], input[name="otp"]'
    SUBMIT_BTN      = 'button[type="submit"], .submit-btn'

    # Booking widget
    PICKUP_INPUT    = '#pickup-location, input[placeholder*="Pickup"], input[placeholder*="pickup"]'
    DEST_INPUT      = '#drop-location, input[placeholder*="Drop"], input[placeholder*="drop"], input[placeholder*="destination"]'
    LOCATION_ITEM   = '.autocomplete-item, .location-suggestion, [class*="suggestion"]'

    # Fare results
    RIDE_CARD       = '.ride-card, [class*="rideCard"], [class*="cab-type"], .category-card'
    RIDE_PRICE      = '[class*="price"], [class*="fare"], .amount, .ride-price'
    RIDE_ETA        = '[class*="eta"], [class*="time"], .ride-time'
    RIDE_NAME       = '[class*="category"], [class*="name"], .ride-type-name, h3, h4'

    LOGGED_IN_CHECK = '.profile-icon, .user-icon, [class*="profile"], .logout-btn'

    # Search button
    SEARCH_BTN      = 'button[class*="search"], .search-ride-btn, #search-cabs-btn'


class OlaScraper(BaseScraper):

    @property
    def platform_name(self) -> str:
        return "Ola"

    def login(self) -> bool:
        if not self.driver:
            self.start_driver()

        if self.cookies_exist():
            self.logger.info("Trying saved Ola cookies...")
            self.load_cookies(OlaSelectors.BASE_URL)
            if self._is_logged_in():
                self.logger.info("✅ Ola cookie login successful!")
                return True

        phone = os.getenv("OLA_PHONE", "")

        return self._credential_login(phone)

    def _is_logged_in(self) -> bool:
        try:
            self.driver.get(OlaSelectors.BASE_URL)
            self._human_delay(2, 3)
            self.driver.find_element(By.CSS_SELECTOR, OlaSelectors.LOGGED_IN_CHECK)
            return True
        except NoSuchElementException:
            return False

    def _credential_login(self, phone: str) -> bool:
        try:
            self.driver.get(OlaSelectors.BASE_URL)
            self._human_delay(2, 3)

            # Click login button
            try:
                self._click(By.CSS_SELECTOR, OlaSelectors.LOGIN_BTN, timeout=5)
                self._human_delay(1, 2)
            except TimeoutException:
                self.logger.info("Login button not found — may already be on login page")

            if phone:
                # Enter phone
                try:
                    phone_field = self._wait_for(By.CSS_SELECTOR, OlaSelectors.PHONE_INPUT)
                    self._type_slowly(phone_field, phone.replace("+91", ""))
                    self._human_delay(0.5, 1)

                    self._click(By.CSS_SELECTOR, OlaSelectors.SUBMIT_BTN)
                    self._human_delay(2, 3)
                except TimeoutException:
                    pass

            self.logger.warning(
                "⚠️  Please complete the login manually in the browser. You have 120s..."
            )
            for _ in range(120):
                if self._is_logged_in():
                    self.save_cookies()
                    self.logger.info("✅ Ola login successful!")
                    return True
                time.sleep(1)

            self.logger.error("❌ Ola login timed out")
            return False

        except Exception as e:
            self.logger.error(f"Ola login error: {e}")
            self._take_screenshot("ola_login_error")
            return False

    def get_fare(self, pickup: str, destination: str) -> dict:
        if not self.driver:
            self.start_driver()

        try:
            self.driver.get(OlaSelectors.BASE_URL)
            self._human_delay(5, 7) # Extra wait for Ola SPA to hydrate

            # Enter pickup
            pickup_field = self._wait_for(By.CSS_SELECTOR, OlaSelectors.PICKUP_INPUT)
            pickup_field.click()
            self._type_slowly(pickup_field, pickup)
            self._human_delay(2, 3)

            items = self.driver.find_elements(By.CSS_SELECTOR, OlaSelectors.LOCATION_ITEM)
            if items:
                items[0].click()
            else:
                pickup_field.send_keys(Keys.ENTER)
            self._human_delay(1, 2)

            # Enter destination
            dest_field = self._wait_for(By.CSS_SELECTOR, OlaSelectors.DEST_INPUT)
            dest_field.click()
            self._type_slowly(dest_field, destination)
            self._human_delay(2, 3)

            items = self.driver.find_elements(By.CSS_SELECTOR, OlaSelectors.LOCATION_ITEM)
            if items:
                items[0].click()
            else:
                dest_field.send_keys(Keys.ENTER)
            self._human_delay(1, 2)

            # Click search / Done
            try:
                self._click(By.CSS_SELECTOR, OlaSelectors.SEARCH_BTN, timeout=5)
            except TimeoutException:
                pass  # May auto-search

            self._human_delay(4, 6)
            return self._parse_fares()

        except TimeoutException:
            self._take_screenshot("ola_fare_timeout")
            return self._build_error_result("Timeout waiting for Ola fare results")
        except Exception as e:
            self._take_screenshot("ola_fare_error")
            return self._build_error_result(str(e))

    def _parse_fares(self) -> dict:
        soup = self._get_page_soup()
        cards = soup.select(OlaSelectors.RIDE_CARD)

        if not cards:
            return self._fallback_parse(soup)

        best_fare = None
        best_min = float("inf")

        for card in cards:
            try:
                price_el = card.select_one(OlaSelectors.RIDE_PRICE)
                eta_el   = card.select_one(OlaSelectors.RIDE_ETA)
                name_el  = card.select_one(OlaSelectors.RIDE_NAME)

                price_text = price_el.get_text(strip=True) if price_el else ""
                eta_text   = eta_el.get_text(strip=True)   if eta_el   else "N/A"
                name_text  = name_el.get_text(strip=True)  if name_el  else "Ola Mini"

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
                self.logger.debug(f"Ola card parse error: {e}")

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
                "ride_type": "Ola Mini",
                "status":    "success",
                "error_msg": "(fallback parser)",
            }
        return self._build_error_result("No Ola fare data found")
