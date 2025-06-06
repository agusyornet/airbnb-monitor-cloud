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
        
        # Check all environment variables for debugging
        airbnb_vars = {k: v for k, v in os.environ.items() if 'AIRBNB' in k}
        for key, value in airbnb_vars.items():
            logger.info(f"Found env var: {key} = {value[:100] if value else 'None'}...")
        
        # Add base URL first
        base_url = os.getenv('AIRBNB_SEARCH_URL')
        if base_url:
            urls.append(base_url)
            logger.info(f"✅ Added base URL: {base_url[:100]}...")
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
        
        logger.info(f"Total unique URLs loaded: {len(unique_urls)}")
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
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--ignore-certificate-errors")
            chrome_options.add_argument("--ignore-ssl-errors")
            chrome_options.add_argument("--ignore-certificate-errors-spki-list")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Try multiple Chrome paths
            chrome_paths = [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable',
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium'
            ]
            
            driver_created = False
            
            # Method 1: Try using system Chrome
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    try:
                        logger.info(f"Trying Chrome at: {chrome_path}")
                        chrome_options.binary_location = chrome_path
                        service = Service(chrome_path)
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                        driver_created = True
                        logger.info(f"✅ WebDriver created successfully using {chrome_path}")
                        break
                    except Exception as e:
                        logger.warning(f"Failed with {chrome_path}: {e}")
                        continue
            
            # Method 2: Use ChromeDriverManager as fallback
            if not driver_created:
                try:
                    logger.info("Trying ChromeDriverManager...")
                    # Create fresh options for ChromeDriverManager
                    fallback_options = Options()
                    fallback_options.add_argument("--headless")
                    fallback_options.add_argument("--no-sandbox")
                    fallback_options.add_argument("--disable-dev-shm-usage")
                    fallback_options.add_argument("--disable-gpu")
                    fallback_options.add_argument("--window-size=1920,1080")
                    fallback_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                    
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=fallback_options)
                    driver_created = True
                    logger.info("✅ WebDriver created successfully using ChromeDriverManager")
                except Exception as e:
                    logger.error(f"ChromeDriverManager also failed: {e}")
            
            # Method 3: Try with system-installed chromedriver
            if not driver_created:
                try:
                    logger.info("Trying system chromedriver...")
                    system_options = Options()
                    system_options.add_argument("--headless")
                    system_options.add_argument("--no-sandbox")
                    system_options.add_argument("--disable-dev-shm-usage")
                    
                    # Try to use system chromedriver
                    self.driver = webdriver.Chrome(options=system_options)
                    driver_created = True
                    logger.info("✅ WebDriver created successfully using system chromedriver")
                except Exception as e:
                    logger.error(f"System chromedriver failed: {e}")
            
            if driver_created:
                # Execute script to remove automation indicators
                try:
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
                    self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
                except:
                    pass  # These are optional
                
                logger.info("✅ WebDriver setup successful")
                return True
            else:
                logger.error("❌ All WebDriver methods failed")
                return False
            
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

    def get_listing_for_url(self, search_url, search_name="Unknown"):
        """Fetch current listings for a specific URL using Selenium"""
        if not self.driver:
            if not self.setup_driver():
                return []
        
        try:
            logger.info(f"=== Loading {search_name} ===")
            logger.info(f"URL: {search_url[:100]}...")
            
            self.driver.get(search_url)
            
            # Wait for page to load
            logger.info("Waiting for page to load...")
            time.sleep(15)
            
            # Get page info
            title = self.driver.title
            current_url = self.driver.current_url
            logger.info(f"Page title: '{title}'")
            logger.info(f"Current URL: {current_url}")
            
            # Wait for listings to load with multiple attempts
            listing_found = False
            wait_selectors = [
                "[data-testid='card-container']",
                "a[href*='/rooms/']",
                "[data-testid='listing-card-title']",
                "div[itemProp='itemListElement']"
            ]
            
            for selector in wait_selectors:
                try:
                    logger.info(f"Waiting for selector: {selector}")
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"✅ Found elements with selector: {selector}")
                    listing_found = True
                    break
                except:
                    logger.warning(f"❌ Timeout waiting for selector: {selector}")
                    continue
            
            if not listing_found:
                logger.warning("No listing elements found with any selector")
                
                # Debug what's actually on the page
                page_source = self.driver.page_source
                logger.info(f"Page source length: {len(page_source)} characters")
                
                # Check for specific indicators
                indicators = [
                    ('data-testid="card-container"', 'card containers'),
                    ('/rooms/', 'room links'),
                    ('no results', 'no results message'),
                    ('search-results', 'search results'),
                    ('Just a moment', 'Cloudflare blocking')
                ]
                
                for indicator, description in indicators:
                    count = page_source.lower().count(indicator.lower())
                    logger.info(f"Page contains '{description}': {count} times")
                
                return []
            
            # Try multiple selectors to find listing cards
            listing_selectors = [
                "[data-testid='card-container']",
                "div[data-testid='card-container']",
                "a[href*='/rooms/']",
                "div[itemProp='itemListElement']"
            ]
            
            current_listings = []
            
            for selector in listing_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"Found {len(elements)} elements with selector: {selector}")
                    
                    if not elements:
                        continue
                    
                    for i, element in enumerate(elements[:20]):  # Limit to first 20
                        try:
                            # Try to extract listing URL and ID
                            if element.tag_name == 'a' and '/rooms/' in element.get_attribute('href'):
                                link_element = element
                                listing_url = element.get_attribute('href')
                            else:
                                link_element = element.find_element(By.CSS_SELECTOR, "a[href*='/rooms/']")
                                listing_url = link_element.get_attribute('href')
                            
                            if listing_url and '/rooms/' in listing_url:
                                # Extract listing ID from URL
                                listing_id = listing_url.split('/rooms/')[-1].split('?')[0].split('/')[0]
                                
                                # Try to get listing title
                                title = None
                                title_selectors = [
                                    "[data-testid='listing-card-title']",
                                    "div[data-testid='listing-card-title']",
                                    ".t1jojoys",
                                    "h3",
                                    ".fb4nyux"
                                ]
                                
                                for title_selector in title_selectors:
                                    try:
                                        title_element = element.find_element(By.CSS_SELECTOR, title_selector)
                                        title = title_element.text.strip()
                                        if title:
                                            break
                                    except:
                                        continue
                                
                                if not title:
                                    title = f"Airbnb Listing {listing_id}"
                                
                                # Try to get price
                                price = "Price not available"
                                price_selectors = [
                                    "[data-testid='price-availability'] span",
                                    "span._1y74zjx",
                                    "span[data-testid='price']",
                                    "div._1jo4hgw span",
                                    "span"
                                ]
                                
                                for price_selector in price_selectors:
                                    try:
                                        price_elements = element.find_elements(By.CSS_SELECTOR, price_selector)
                                        for price_element in price_elements:
                                            price_text = price_element.text.strip()
                                            if price_text and any(currency in price_text for currency in ['kr', '$', '€', '£', 'DKK', 'SEK', 'EUR', '₹', '¥']):
                                                price = price_text
                                                break
                                        if price != "Price not available":
                                            break
                                    except:
                                        continue
                                
                                # Try to get image
                                image_url = None
                                image_selectors = [
                                    "img[data-testid='listing-card-image']",
                                    "img[data-original]",
                                    "img[src*='airbnb']",
                                    "picture img",
                                    "img"
                                ]
                                
                                for img_selector in image_selectors:
                                    try:
                                        img_element = element.find_element(By.CSS_SELECTOR, img_selector)
                                        src = img_element.get_attribute('src') or img_element.get_attribute('data-original')
                                        if src and ('airbnb' in src or 'https://' in src):
                                            image_url = src
                                            break
                                    except:
                                        continue
                                
                                if listing_id and len(listing_id) > 3:  # Valid listing ID
                                    current_listings.append({
                                        'id': listing_id,
                                        'name': title,
                                        'url': listing_url,
                                        'price': price,
                                        'image_url': image_url,
                                        'search_name': search_name
                                    })
                                    logger.info(f"✅ Extracted listing: {listing_id} - {title}")
                        
                        except Exception as e:
                            continue  # Skip this element if we can't extract data
                    
                    if current_listings:
                        logger.info(f"Successfully extracted {len(current_listings)} listings using selector: {selector}")
                        break  # If we found listings with this selector, stop trying others
                        
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # Remove duplicates based on ID
            seen_ids = set()
            unique_listings = []
            for listing in current_listings:
                if listing['id'] not in seen_ids:
                    seen_ids.add(listing['id'])
                    unique_listings.append(listing)
            
            logger.info(f"Final result: {len(unique_listings)} unique listings for {search_name}")
            return unique_listings
            
        except Exception as e:
            logger.error(f"Error fetching listings for {search_name}: {e}")
            return []

    def get_listings(self):
        """Get listings from all search URLs"""
        all_listings = []
        
        for i, search_url in enumerate(self.search_urls, 1):
            search_name = f"Search {i}"
            logger.info(f"=== Processing {search_name} ===")
            
            listings = self.get_listing_for_url(search_url, search_name)
            all_listings.extend(listings)
            
            # Add delay between requests
            if i < len(self.search_urls):
                logger.info("Waiting 10 seconds before next search...")
                time.sleep(10)

        logger.info(f"Total listings found across all searches: {len(all_listings)}")
        return all_listings
    
    def send_notification(self, new_listings):
        """Send email notification for new listings"""
        if not new_listings:
            return
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = f"🏠 {len(new_listings)} New Airbnb Listing(s) Found!"
            
            # Group listings by search
            listings_by_search = {}
            for listing in new_listings:
                search_name = listing.get('search_name', 'Unknown Search')
                if search_name not in listings_by_search:
                    listings_by_search[search_name] = []
                listings_by_search[search_name].append(listing)
            
            # Create email body
            body = f"""
            <h2>🤖 New Airbnb Listings Found by GitHub Actions!</h2>
            <p>Found {len(new_listings)} new listing(s) across {len(listings_by_search)} search(es):</p>
            <br>
            """
            
            for search_name, search_listings in listings_by_search.items():
                body += f"""<h3 style="color: #ff5a5f; margin: 25px 0 15px 0;">📍 {search_name} ({len(search_listings)} new)</h3>"""
                
                for listing in search_listings:
                    clean_name = listing['name'].encode('ascii', 'ignore').decode('ascii') if listing['name'] else f"Listing {listing['id']}"
                    price_display = listing.get('price', 'Price not available')
                    image_url = listing.get('image_url', '')
                    
                    listing_html = f"""
                    <div style="border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 8px; background-color: #fafafa;">
                        <div style="display: flex; align-items: flex-start; gap: 15px;">
                    """
                    
                    if image_url:
                        listing_html += f"""
                            <div style="flex-shrink: 0;">
                                <img src="{image_url}" alt="Property image" style="width: 120px; height: 90px; object-fit: cover; border-radius: 6px; border: 1px solid #ddd;">
                            </div>
                        """
                    
                    listing_html += f"""
                            <div style="flex-grow: 1;">
                                <h3 style="margin: 0 0 8px 0; color: #222; font-size: 16px;">{clean_name}</h3>
                                <p style="margin: 5px 0; color: #666; font-size: 14px;"><strong>Price:</strong> <span style="color: #ff5a5f; font-weight: bold;">{price_display}</span></p>
                                <p style="margin: 5px 0; color: #666; font-size: 14px;"><strong>ID:</strong> {listing['id']}</p>
                                <p style="margin: 10px 0 0 0;"><a href="{listing['url']}" style="color: #ff5a5f; text-decoration: none; font-weight: bold; background-color: #fff; padding: 8px 16px; border: 2px solid #ff5a5f; border-radius: 4px; display: inline-block;">📍 View Listing</a></p>
                            </div>
                        </div>
                    </div>
                    """
                    
                    body += listing_html
            
            body += f"""
            <br>
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This email was generated by your Airbnb Monitor running on GitHub Actions.<br>
                Monitoring timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
            </p>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent for {len(new_listings)} new listings")
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
    
    def check_for_new_listings(self):
        """Main function to check for new listings"""
        logger.info(f"🤖 GitHub Actions: Checking for new listings across {len(self.search_urls)} search URL(s)...")
        
        if not self.search_urls:
            logger.error("No search URLs configured!")
            return
        
        current_listings = self.get_listings()
        if not current_listings:
            logger.warning("No listings found across all searches")
            return
        
        new_listings = []
        current_ids = set()
        
        for listing in current_listings:
            listing_id = listing['id']
            current_ids.add(listing_id)
            
            if listing_id not in self.seen_listings:
                new_listings.append(listing)
                logger.info(f"New listing found: {listing['name']} (ID: {listing_id})")
        
        # Update seen listings
        self.seen_listings.update(current_ids)
        self.save_seen_listings()
        
        # Send notification if new listings found
        if new_listings:
            self.send_notification(new_listings)
            logger.info(f"Found {len(new_listings)} new listings across all searches")
        else:
            logger.info("No new listings found across any searches")
    
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
    
    monitor = AirbnbMonitorGitHub()
    
    if not monitor.search_urls:
        logger.error("No search URLs found. Please set AIRBNB_SEARCH_URL or AIRBNB_SEARCH_URL_1, AIRBNB_SEARCH_URL_2, etc.")
        return
        
    monitor.run_once()

if __name__ == "__main__":
    main()