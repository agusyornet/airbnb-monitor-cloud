import json
import smtplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AirbnbMonitorGitHub:
    def __init__(self):
        # Email configuration
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # File to store previously seen listings
        self.data_file = 'seen_listings.json'
        
        # Load search URLs - include base URL and numbered URLs
        self.search_urls = self.load_search_urls()
        
        # Load previously seen listings
        self.seen_listings = self.load_seen_listings()
        
        # WebDriver setup
        self.driver = None
    
    def load_search_urls(self):
        """Load search URLs from environment variables"""
        urls = []
        
        logger.info("=== DEBUG: Checking environment variables ===")
        
        # Check all environment variables that might be URLs
        for key, value in os.environ.items():
            if 'AIRBNB' in key:
                logger.info(f"Found env var: {key} = {value[:100] if value else 'None'}...")
        
        # Add base URL first
        base_url = os.getenv('AIRBNB_SEARCH_URL')
        if base_url:
            urls.append(base_url)
            logger.info(f"✅ Added base URL (AIRBNB_SEARCH_URL): {base_url[:100]}...")
        else:
            logger.warning("❌ No AIRBNB_SEARCH_URL found")
        
        # Add numbered URLs - check 1 through 10
        for i in range(1, 11):
            url_key = f"AIRBNB_SEARCH_URL_{i}"
            url = os.getenv(url_key)
            if url:
                urls.append(url)
                logger.info(f"✅ Added {url_key}: {url[:100]}...")
            else:
                logger.debug(f"❌ No {url_key} found")
        
        # Remove duplicates while preserving order
        unique_urls = []
        seen = set()
        for url in urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
        
        logger.info(f"=== TOTAL UNIQUE URLs LOADED: {len(unique_urls)} ===")
        for i, url in enumerate(unique_urls, 1):
            logger.info(f"URL {i}: {url}")
        
        return unique_urls
    
    def setup_driver(self):
        """Set up Chrome WebDriver for GitHub Actions"""
        try:
            chrome_options = Options()
            
            # GitHub Actions specific options
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Use the system Chrome
            service = Service('/usr/bin/google-chrome')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ WebDriver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up WebDriver: {e}")
            return False
    
    def load_seen_listings(self):
        """Load previously seen listings from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        seen = set(data)
                    else:
                        seen = set(data.get('seen_listings', []))
                    logger.info(f"Loaded {len(seen)} previously seen listings")
                    return seen
        except Exception as e:
            logger.error(f"Error loading seen listings: {e}")
        
        return set()
    
    def save_seen_listings(self):
        """Save seen listings to file"""
        try:
            data = {
                'seen_listings': list(self.seen_listings),
                'last_updated': datetime.now().isoformat(),
                'total_urls': len(self.search_urls)
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.seen_listings)} seen listings to file")
        except Exception as e:
            logger.error(f"Error saving seen listings: {e}")

    def test_page_load(self, search_url, search_name="Test"):
        """Simple test to see if we can load the page and find basic elements"""
        if not self.driver:
            if not self.setup_driver():
                return False
        
        try:
            logger.info(f"=== TESTING PAGE LOAD FOR {search_name} ===")
            logger.info(f"URL: {search_url}")
            
            # Load the page
            logger.info("Loading page...")
            self.driver.get(search_url)
            
            # Wait for page to load
            time.sleep(15)
            
            # Get basic page info
            title = self.driver.title
            current_url = self.driver.current_url
            logger.info(f"Page title: '{title}'")
            logger.info(f"Current URL: {current_url}")
            
            # Check for basic elements
            selectors_to_test = [
                "[data-testid='card-container']",
                "a[href*='/rooms/']", 
                "[data-testid='listing-card-title']",
                "div[itemProp='itemListElement']",
                ".no-results",
                "[data-testid='stays-search-results-section']"
            ]
            
            found_elements = {}
            for selector in selectors_to_test:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    found_elements[selector] = len(elements)
                    logger.info(f"Selector '{selector}': {len(elements)} elements")
                except Exception as e:
                    found_elements[selector] = f"Error: {e}"
                    logger.error(f"Selector '{selector}': Error - {e}")
            
            # Check page source for clues
            page_source = self.driver.page_source
            logger.info(f"Page source length: {len(page_source)} characters")
            
            # Look for specific Airbnb indicators
            airbnb_indicators = [
                'data-testid="card-container"',
                '/rooms/',
                'listing-card',
                'no results',
                'search-results',
                'stays-search'
            ]
            
            for indicator in airbnb_indicators:
                count = page_source.lower().count(indicator.lower())
                logger.info(f"Page contains '{indicator}': {count} times")
            
            # Return True if we found any room links
            room_links = found_elements.get("a[href*='/rooms/']", 0)
            if isinstance(room_links, int) and room_links > 0:
                logger.info(f"✅ SUCCESS: Found {room_links} room links on page")
                return True
            else:
                logger.warning(f"❌ ISSUE: No room links found on page")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error testing page load: {e}")
            return False

    def check_for_new_listings(self):
        """Main function to check for new listings"""
        logger.info(f"🤖 GitHub Actions: Starting URL validation for {len(self.search_urls)} search URL(s)...")
        
        if not self.search_urls:
            logger.error("❌ CRITICAL: No search URLs configured!")
            logger.error("Please check your GitHub secrets:")
            logger.error("- AIRBNB_SEARCH_URL (base URL)")
            logger.error("- AIRBNB_SEARCH_URL_2, AIRBNB_SEARCH_URL_3, etc. (additional URLs)")
            return
        
        # Test each URL
        working_urls = 0
        for i, search_url in enumerate(self.search_urls, 1):
            search_name = f"Search {i}"
            logger.info(f"\n=== TESTING {search_name} ===")
            
            if self.test_page_load(search_url, search_name):
                working_urls += 1
                logger.info(f"✅ {search_name}: SUCCESS")
            else:
                logger.warning(f"❌ {search_name}: FAILED")
            
            # Small delay between tests
            time.sleep(5)
        
        logger.info(f"\n=== FINAL RESULTS ===")
        logger.info(f"Total URLs tested: {len(self.search_urls)}")
        logger.info(f"Working URLs: {working_urls}")
        logger.info(f"Failed URLs: {len(self.search_urls) - working_urls}")
        
        if working_urls == 0:
            logger.error("❌ CRITICAL: No URLs are working!")
            logger.error("This could be due to:")
            logger.error("1. Airbnb blocking automated access")
            logger.error("2. Invalid/expired URLs")
            logger.error("3. Network issues")
            logger.error("4. URL returning 'no results'")
        else:
            logger.info(f"✅ SUCCESS: {working_urls} URL(s) are working")
    
    def run_once(self):
        """Run the monitor once (for GitHub Actions)"""
        try:
            self.check_for_new_listings()
        except Exception as e:
            logger.error(f"Error in monitoring: {e}")
        finally:
            if self.driver:
                self.driver.quit()

def main():
    # Verify required environment variables
    required_vars = ['SENDER_EMAIL', 'SENDER_PASSWORD', 'RECIPIENT_EMAIL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return
    
    logger.info("=== STARTING AIRBNB MONITOR DEBUG TEST ===")
    
    monitor = AirbnbMonitorGitHub()
    
    if not monitor.search_urls:
        logger.error("No search URLs found. Please set AIRBNB_SEARCH_URL or AIRBNB_SEARCH_URL_1, AIRBNB_SEARCH_URL_2, etc.")
        return
        
    monitor.run_once()

if __name__ == "__main__":
    main()
