import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from scrapers.uber_scraper import UberScraper, UberSelectors
from scrapers.ola_scraper import OlaScraper, OlaSelectors
from scrapers.rapido_scraper import RapidoScraper, RapidoSelectors

def login_uber():
    print("--- UBER LOGIN ---")
    phone = input("Enter Uber phone number: ").strip()
    u = UberScraper(headless=True)
    u.start_driver()
    try:
        u.driver.get(UberSelectors.LOGIN_URL)
        time.sleep(5)
        
        try:
            phone_field = u._wait_for(By.CSS_SELECTOR, UberSelectors.PHONE_INPUT, timeout=5)
            u._type_slowly(phone_field, phone)
            u._click(By.CSS_SELECTOR, UberSelectors.NEXT_BTN)
            time.sleep(3)
        except Exception as e:
            with open("debug_uber.html", "w", encoding="utf-8") as f:
                f.write(u.driver.page_source)
            print("Failed to find phone input! Page source saved to debug_uber.html.")
            raise e
        
        # Try password or OTP
        try:
            pwd_field = u._wait_for(By.CSS_SELECTOR, UberSelectors.PASSWORD_INPUT, timeout=5)
            pwd = input("Enter Uber password: ").strip()
            u._type_slowly(pwd_field, pwd)
            u._click(By.CSS_SELECTOR, UberSelectors.NEXT_BTN)
            time.sleep(5)
        except:
            print("Password field not found, assuming OTP flow.")
            pass
            
        print("Please check your phone for the OTP or wait for the page to load.")
        otp = input("Enter Uber OTP (if required, else press enter): ").strip()
        if otp:
            try:
                otp_field = u._wait_for(By.CSS_SELECTOR, UberSelectors.OTP_INPUT, timeout=5)
                u._type_slowly(otp_field, otp)
                time.sleep(5)
            except Exception as e:
                print("Could not enter OTP: ", e)
                
        # Wait until logged in
        for i in range(20):
            if u._is_logged_in():
                u.save_cookies()
                print("Uber Login SUCCESS! Cookies saved.")
                break
            time.sleep(1)
        else:
            print("Uber Login FAILED.")
    finally:
        u.quit_driver()

def login_ola():
    print("--- OLA LOGIN ---")
    phone = input("Enter Ola phone number: ").strip()
    o = OlaScraper(headless=True)
    o.start_driver()
    try:
        o.driver.get(OlaSelectors.BASE_URL)
        time.sleep(3)
        try:
            o._click(By.CSS_SELECTOR, OlaSelectors.LOGIN_BTN, timeout=5)
            time.sleep(2)
        except:
            pass
        
        phone_field = o._wait_for(By.CSS_SELECTOR, OlaSelectors.PHONE_INPUT)
        o._type_slowly(phone_field, phone.replace("+91", ""))
        o._click(By.CSS_SELECTOR, OlaSelectors.SUBMIT_BTN)
        time.sleep(3)
        
        otp = input("Enter Ola OTP: ").strip()
        if otp:
            # Ola usually handles OTP automatically as you type or you have to find the input
            # Typically it's a single input or 4 inputs. We can just send keys to body or find input
            try:
                # Find any input that might be OTP
                otp_field = o.driver.find_element(By.CSS_SELECTOR, "input[type='number'], input[maxlength='4']")
                o._type_slowly(otp_field, otp)
                time.sleep(2)
                # Try clicking submit or verify
                try:
                    o.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                except:
                    pass
            except Exception as e:
                print("Could not enter OTP: ", e)
                
        for i in range(20):
            if o._is_logged_in():
                o.save_cookies()
                print("Ola Login SUCCESS! Cookies saved.")
                break
            time.sleep(1)
        else:
            print("Ola Login FAILED.")
    finally:
        o.quit_driver()

def login_rapido():
    print("--- RAPIDO LOGIN ---")
    phone = input("Enter Rapido phone number: ").strip()
    r = RapidoScraper(headless=True)
    r.start_driver()
    try:
        r.driver.get(RapidoSelectors.BASE_URL)
        time.sleep(3)
        
        # Rapido: type in pickup to trigger modal
        # To trigger login on Rapido, we usually need to try booking a ride first.
        try:
            # Enter dummy pickup
            pickup = r._wait_for(By.CSS_SELECTOR, RapidoSelectors.PICKUP_INPUT)
            r._type_slowly(pickup, "Jaipur")
            time.sleep(2)
            pickup.send_keys(Keys.ENTER)
            
            # Enter dummy drop
            drop = r._wait_for(By.CSS_SELECTOR, RapidoSelectors.DEST_INPUT)
            r._type_slowly(drop, "Delhi")
            time.sleep(2)
            drop.send_keys(Keys.ENTER)
            
            # Click Book Ride using JS click to avoid intercept
            search_btn = r.driver.find_element(By.CSS_SELECTOR, RapidoSelectors.SEARCH_BTN)
            r.driver.execute_script("arguments[0].click();", search_btn)
            time.sleep(3)
        except Exception as e:
            print("Could not trigger login via Book Ride:", e)
            time.sleep(3)
            
        try:
            phone_field = r._wait_for(By.CSS_SELECTOR, RapidoSelectors.PHONE_INPUT, timeout=5)
            r._type_slowly(phone_field, phone)
            
            # send otp
            try:
                r._click(By.CSS_SELECTOR, RapidoSelectors.SEND_OTP_BTN, timeout=3)
            except:
                phone_field.send_keys("\n")
            time.sleep(3)
            
            otp = input("Enter Rapido OTP: ").strip()
            if otp:
                # Usually Rapido has a generic input for OTP or 4/6 boxes
                # Since we are headless we can try to send it to the active element
                r.driver.switch_to.active_element.send_keys(otp)
                time.sleep(1)
                r.driver.switch_to.active_element.send_keys("\n")
        except Exception as e:
            with open("debug_rapido.html", "w", encoding="utf-8") as f:
                f.write(r.driver.page_source)
            print("Error triggering Rapido login modal:", e)
            raise e
            
        time.sleep(5)
        # Check if popup is gone
        try:
            r.driver.find_element(By.CSS_SELECTOR, RapidoSelectors.PHONE_INPUT)
            print("Rapido Login FAILED.")
        except:
            r.save_cookies()
            print("Rapido Login SUCCESS! Cookies saved.")
    finally:
        r.quit_driver()

if __name__ == "__main__":
    platform = sys.argv[1].lower() if len(sys.argv) > 1 else "uber"
    if platform == "uber":
        login_uber()
    elif platform == "ola":
        login_ola()
    elif platform == "rapido":
        login_rapido()
    else:
        print("Unsupported platform")
