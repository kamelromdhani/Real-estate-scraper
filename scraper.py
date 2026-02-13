"""
Core web scraping module for Tayara.tn Real Estate Listings

This module contains all the scraping logic, including:
- Page fetching with retry logic
- HTML parsing
- Data extraction and normalization
- Pagination handling
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
from urllib.parse import urljoin, urlparse, parse_qs
import json


import config

# Configure module logger
logger = logging.getLogger(__name__)


class TayaraScraper:
    """
    Main scraper class for extracting real estate listings from Tayara.tn
    
    This class handles:
    - Session management
    - Request throttling
    - HTML parsing
    - Data extraction and normalization
    """
    
    def __init__(self):
        """Initialize the scraper with session and configuration"""
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        self.listings_scraped = 0
        self.errors_encountered = 0
        
        logger.info("Tayara scraper initialized")
    
    def _make_request(self, url: str, retry_count: int = 0) -> Optional[requests.Response]:
        """
        Make HTTP request with retry logic and exponential backoff
        
        Args:
            url: URL to fetch
            retry_count: Current retry attempt number
            
        Returns:
            Response object or None if all retries failed
        """
        try:
            # Add polite delay between requests
            delay = random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)
            time.sleep(delay)
            
            logger.debug(f"Requesting URL: {url}")
            response = self.session.get(
                url,
                timeout=config.REQUEST_TIMEOUT,
                allow_redirects=True
            )
            
            # Check for successful response
            response.raise_for_status()
            
            # Verify we got HTML content
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                logger.warning(f"Unexpected content type: {content_type}")
            
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {str(e)}")
            
            # Retry logic with exponential backoff
            if retry_count < config.MAX_RETRIES:
                backoff_time = config.BACKOFF_FACTOR ** retry_count
                logger.info(f"Retrying in {backoff_time} seconds... (Attempt {retry_count + 1}/{config.MAX_RETRIES})")
                time.sleep(backoff_time)
                return self._make_request(url, retry_count + 1)
            else:
                logger.error(f"Max retries reached for {url}")
                self.errors_encountered += 1
                return None
    
    def get_listing_links(self, page: int = 1) -> Tuple[List[str], bool]:
        """
        Extract all listing URLs from a search results page
        
        Args:
            page: Page number to scrape
            
        Returns:
            Tuple of (list of listing URLs, has_next_page boolean)
            
        Selector Strategy:
        - Tayara typically uses <a> tags with specific classes for listing cards
        - Common patterns: class="listing-card", "ad-card", or data-testid attributes
        - Links often contain "/ad/" or "/ads/" in the URL
        - Need to handle both relative and absolute URLs
        """
        # Construct pagination URL
        if page == 1:
            url = config.IMMOBILIER_URL
        else:
            # Tayara typically uses ?page=N for pagination
            url = f"{config.IMMOBILIER_URL}?page={page}"
        
        response = self._make_request(url)
        if not response:
            return [], False
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Save HTML snapshot for debugging if enabled
        if config.SAVE_HTML_SNAPSHOTS:
            snapshot_path = config.RAW_DATA_DIR / f"page_{page}.html"
            snapshot_path.write_text(response.text, encoding='utf-8')
            logger.debug(f"Saved HTML snapshot: {snapshot_path}")
        
        listing_links = []
        
        # Strategy 1: Look for links containing "/ad/" or "/item/" (most reliable)
        # This catches individual listing pages regardless of HTML structure changes
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link['href']
            # Check if this looks like a listing URL
            # Old format: /ad/12345
            # New format: /item/.../.../slug/id/
            if '/ad/' in href or '/ads/' in href or '/item/' in href:
                # Avoid category pages, search pages, etc.
                if '/c/' not in href and 'page=' not in href and 'search' not in href.lower():
                    full_url = urljoin(config.BASE_URL, href)
                    if full_url not in listing_links:
                        listing_links.append(full_url)

        
        # Strategy 2: Look for common listing card classes (backup)
        # Tayara and similar sites often use specific classes for ad cards
        if not listing_links:
            logger.warning("Strategy 1 failed, trying common class patterns")
            card_selectors = [
                {'class_': re.compile(r'ad-card|listing-card|item-card')},
                {'data-testid': re.compile(r'ad-|listing-')},
                {'class_': re.compile(r'card.*link|link.*card')},
            ]
            
            for selector in card_selectors:
                cards = soup.find_all('a', selector)
                for card in cards:
                    href = card.get('href', '')
                    if href:
                        full_url = urljoin(config.BASE_URL, href)
                        if full_url not in listing_links:
                            listing_links.append(full_url)
                if listing_links:
                    break
        
        # Detect if there's a next page
        # Default strategy: If we found listings, assume there is a next page
        # The scrape_all loop will verify if the next page is valid (404 check) or empty
        has_next_page = len(listing_links) > 0
        
        # Look for pagination elements (optional confirmation)
        pagination = soup.find_all(['a', 'button'], text=re.compile(r'suivant|next|›|»', re.IGNORECASE))
        if pagination:
            has_next_page = True
        
        # Alternative: Check if there's a link to the next page number
        next_page_num = page + 1
        next_page_links = soup.find_all('a', href=re.compile(f'page={next_page_num}'))
        if next_page_links:
            has_next_page = True
        
        # If we found very few listings, might be last page
        # Only stop if we found significantly fewer than expected
        if len(listing_links) < 5:
            has_next_page = False
        
        logger.info(f"Page {page}: Found {len(listing_links)} listings, has_next={has_next_page}")
        
        return listing_links, has_next_page
    
    def parse_listing(self, url: str) -> Optional[Dict]:
        """
        Parse a single listing page and extract all relevant data
        
        Args:
            url: URL of the listing to scrape
            
        Returns:
            Dictionary containing all extracted fields, or None if parsing failed
            
        Extraction Strategy:
        1. Title: Usually in <h1> or meta tags
        2. Price: Look for price class, numeric patterns, currency symbols
        3. Description: Main content area, often in <p> or specific div
        4. Location: Often in breadcrumbs, metadata, or specific location div
        5. Criteria: Key-value pairs in tables, lists, or definition lists
        6. Images: <img> tags in gallery or carousel
        7. Date: Posted date in metadata or time elements
        """
        response = self._make_request(url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Initialize data dictionary
        data = {
            'listing_url': url,
            'scraped_at': datetime.now().isoformat(),
        }
        
        # Try extraction from Next.js data (most reliable)
        next_data = self._extract_next_data(soup)
        if next_data:
            logger.info(f"Using Next.js data for listing: {url}")
            # Merge with base data
            data.update(next_data)
            
            # Additional processing/normalization if needed
            if 'image_urls' in next_data:
                data['image_count'] = len(next_data['image_urls'])
                
            return data

        # Legacy/Fallback extraction strategies
        
        # Extract listing ID (if available in URL or data attributes)
        data['listing_id'] = self._extract_listing_id(url, soup)

        
        # Extract title
        data['title'] = self._extract_title(soup)
        
        # Extract price and currency
        price_data = self._extract_price(soup)
        data.update(price_data)
        
        # Extract category
        data['category'] = self._extract_category(soup, url)
        
        # Extract location
        location_data = self._extract_location(soup)
        data.update(location_data)
        
        # Extract description
        data['description'] = self._extract_description(soup)
        
        # Extract date posted
        data['date_posted'] = self._extract_date(soup)
        
        # Extract criteria/features
        criteria = self._extract_criteria(soup)
        data['criteria'] = criteria
        
        # Flatten important criteria to top level
        if criteria:
            for key in ['surface', 'rooms', 'bedrooms', 'bathrooms']:
                if key in criteria:
                    data[key] = criteria[key]
        
        # Extract image URLs
        data['image_urls'] = self._extract_images(soup)
        data['image_count'] = len(data['image_urls'])
        
        # Data quality check
        if config.ENABLE_DATA_VALIDATION:
            if not self._validate_listing(data):
                logger.warning(f"Listing failed validation: {url}")
                return None
        
        self.listings_scraped += 1
        logger.info(f"Successfully parsed listing {self.listings_scraped}: {data.get('title', 'N/A')[:50]}")
        
        return data
    
        return data
    
    def _extract_next_data(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract data from Next.js __NEXT_DATA__ script"""
        try:
            script_tag = soup.find('script', id='__NEXT_DATA__')
            if not script_tag:
                return None
            
            json_data = json.loads(script_tag.string)
            ad_details = json_data.get('props', {}).get('pageProps', {}).get('adDetails', {})
            
            if not ad_details:
                return None
                
            # Map Next.js data to our schema
            extracted = {
                'listing_id': ad_details.get('id'),
                'title': ad_details.get('title'),
                'description': ad_details.get('description'),
                'price_numeric': float(ad_details.get('price', 0)) if ad_details.get('price') is not None else None,
                'price_raw': f"{ad_details.get('price')} DT" if ad_details.get('price') else "N/A",
                'currency': 'TND', # Tayara is TN only
                'category': ad_details.get('category'),
                'date_posted': ad_details.get('publishedOn'),
                'image_urls': [img if img.startswith('http') else urljoin(config.BASE_URL, img) for img in ad_details.get('images', [])],
            }
            
            # Location
            loc = ad_details.get('location', {})
            extracted['city'] = loc.get('delegation')
            extracted['governorate'] = loc.get('governorate')
            extracted['location_raw'] = f"{extracted['city']}, {extracted['governorate']}"
            
            # Criteria
            criteria = {}
            for param in ad_details.get('adParams', []):
                key = self._normalize_criteria_key(param.get('label', ''))
                value = param.get('value')
                criteria[key] = value
                
            extracted['criteria'] = self._normalize_criteria_values(criteria)
            
            # Top level criteria keys
            for key in ['surface', 'rooms', 'bedrooms', 'bathrooms']:
                if key in extracted['criteria']:
                    extracted[key] = extracted['criteria'][key]
                    
            return extracted
            
        except Exception as e:
            logger.warning(f"Failed to extract Next.js data: {e}")
            return None

    def _extract_listing_id(self, url: str, soup: BeautifulSoup) -> str:

        """
        Extract or generate a unique listing ID
        
        Priority:
        1. ID from URL pattern (e.g., /ad/123456/)
        2. data-id or id attribute
        3. Generate stable hash from URL
        """
        # Try to extract from URL
        # Old format: /ad/(\d+)
        match = re.search(r'/ad/(\d+)', url)
        if match:
            return match.group(1)
        
        # New format: /item/.../ID/ or /item/.../ID
        # Example: https://www.tayara.tn/item/category/city/location/slug/695e2444a5f53ffb7c90cf92/
        if '/item/' in url:
            # Extract the last segment that looks like an ID (alphanumeric, long)
            # Remove trailing slash if present
            clean_url = url.rstrip('/')
            parts = clean_url.split('/')
            last_part = parts[-1]
            
            # Check if it looks like a Mongo ObjectID (24 hex chars) or similar hash
            if re.match(r'^[a-f0-9]{24}$', last_part, re.IGNORECASE):
                return last_part
            
            # Fallback for other ID types (numeric, etc) if found at end
            if last_part.isalnum():
                return last_part

        
        # Try to find in HTML attributes
        id_patterns = [
            soup.find(attrs={'data-ad-id': True}),
            soup.find(attrs={'data-listing-id': True}),
            soup.find(id=re.compile(r'ad-\d+|listing-\d+')),
        ]
        
        for element in id_patterns:
            if element:
                # Extract numeric ID from attribute value
                id_value = str(element.get('data-ad-id') or element.get('data-listing-id') or element.get('id'))
                match = re.search(r'\d+', id_value)
                if match:
                    return match.group(0)
        
        # Fallback: Generate stable hash from URL
        # Use last part of URL path for more readable ID
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"hash_{url_hash}"
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract listing title"""
        # Strategy 1: <h1> tag (most common)
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        # Strategy 2: Meta tags
        meta_title = soup.find('meta', property='og:title')
        if meta_title:
            return meta_title.get('content', '').strip()
        
        # Strategy 3: Title tag
        title_tag = soup.find('title')
        if title_tag:
            # Remove site name suffix (common pattern: "Title - Tayara.tn")
            title = title_tag.get_text(strip=True)
            return re.sub(r'\s*[-|]\s*Tayara.*$', '', title, flags=re.IGNORECASE)
        
        return "N/A"
    
    def _extract_price(self, soup: BeautifulSoup) -> Dict:
        """
        Extract price and currency
        
        Returns dict with: price_raw, price_numeric, currency
        """
        result = {
            'price_raw': 'N/A',
            'price_numeric': None,
            'currency': 'TND'  # Default for Tunisia
        }
        
        # Common price selectors
        price_selectors = [
            {'class_': re.compile(r'price|prix', re.IGNORECASE)},
            {'itemprop': 'price'},
            {'data-testid': re.compile(r'price')},
        ]
        
        price_element = None
        for selector in price_selectors:
            price_element = soup.find(['span', 'div', 'p', 'strong'], selector)
            if price_element:
                break
        
        if not price_element:
            # Fallback: Look for text with currency symbols
            text = soup.get_text()
            price_match = re.search(r'(\d[\d\s.,]*)\s*(TND|DT|dt|€|EUR|\$|USD)', text, re.IGNORECASE)
            if price_match:
                result['price_raw'] = price_match.group(0)
                result['price_numeric'] = self._parse_numeric_price(price_match.group(1))
                result['currency'] = self._normalize_currency(price_match.group(2))
            return result
        
        price_text = price_element.get_text(strip=True)
        result['price_raw'] = price_text
        
        # Extract numeric value and currency
        # Pattern: "123,456.78 TND" or "123 456 DT"
        numbers = re.findall(r'\d+', price_text.replace(',', '').replace(' ', ''))
        if numbers:
            result['price_numeric'] = float(''.join(numbers))
        
        # Extract currency
        for symbol, normalized in config.CURRENCY_SYMBOLS.items():
            if symbol.lower() in price_text.lower():
                result['currency'] = normalized
                break
        
        return result
    
    def _parse_numeric_price(self, price_str: str) -> Optional[float]:
        """Convert price string to numeric value"""
        try:
            # Remove spaces, handle both comma and period as decimal separator
            cleaned = price_str.replace(' ', '').replace(',', '')
            return float(cleaned)
        except (ValueError, AttributeError):
            return None
    
    def _normalize_currency(self, currency_str: str) -> str:
        """Normalize currency symbol to standard code"""
        return config.CURRENCY_SYMBOLS.get(currency_str, currency_str.upper())
    
    def _extract_category(self, soup: BeautifulSoup, url: str) -> str:
        """Extract and normalize listing category"""
        category = "N/A"
        
        # Strategy 1: Breadcrumbs
        breadcrumbs = soup.find_all(['nav', 'ol', 'ul'], class_=re.compile(r'breadcrumb'))
        if breadcrumbs:
            links = breadcrumbs[0].find_all('a')
            if links:
                # Usually last or second-to-last is the category
                category_text = links[-1].get_text(strip=True).lower()
                category = self._normalize_category(category_text)
        
        # Strategy 2: Category meta tag or data attribute
        if category == "N/A":
            cat_element = soup.find(attrs={'data-category': True})
            if cat_element:
                category = self._normalize_category(cat_element['data-category'])
        
        # Strategy 3: URL analysis
        if category == "N/A":
            url_lower = url.lower()
            for key in config.CATEGORY_MAPPINGS.keys():
                if key in url_lower:
                    category = config.CATEGORY_MAPPINGS[key]
                    break
        
        return category
    
    def _normalize_category(self, category_text: str) -> str:
        """Normalize category to standard values"""
        category_lower = category_text.lower().strip()
        return config.CATEGORY_MAPPINGS.get(category_lower, category_text)
    
    def _extract_location(self, soup: BeautifulSoup) -> Dict:
        """
        Extract location information
        
        Returns dict with: location_raw, city, governorate, neighborhood
        """
        result = {
            'location_raw': 'N/A',
            'city': None,
            'governorate': None,
            'neighborhood': None,
        }
        
        # Common location selectors
        location_selectors = [
            {'class_': re.compile(r'location|localisation|address|ville', re.IGNORECASE)},
            {'itemprop': 'address'},
            {'data-testid': re.compile(r'location')},
        ]
        
        location_element = None
        for selector in location_selectors:
            location_element = soup.find(['span', 'div', 'p', 'address'], selector)
            if location_element:
                break
        
        if location_element:
            location_text = location_element.get_text(strip=True)
            result['location_raw'] = location_text
            
            # Try to parse structured location (e.g., "Tunis, Ariana, Ennasr")
            parts = [p.strip() for p in location_text.split(',')]
            if len(parts) >= 2:
                result['governorate'] = parts[0]
                result['city'] = parts[1]
                if len(parts) >= 3:
                    result['neighborhood'] = parts[2]
            elif len(parts) == 1:
                result['city'] = parts[0]
        
        return result
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract full listing description"""
        # Common description selectors
        desc_selectors = [
            {'class_': re.compile(r'description|desc|content|detail', re.IGNORECASE)},
            {'itemprop': 'description'},
            {'data-testid': re.compile(r'description')},
        ]
        
        for selector in desc_selectors:
            desc_element = soup.find(['div', 'section', 'article', 'p'], selector)
            if desc_element:
                # Get text, preserving paragraphs with newlines
                paragraphs = desc_element.find_all('p')
                if paragraphs:
                    return '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                else:
                    return desc_element.get_text(strip=True)
        
        # Fallback: Look for meta description
        meta_desc = soup.find('meta', property='og:description')
        if meta_desc:
            return meta_desc.get('content', 'N/A')
        
        return "N/A"
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract posting date and normalize to ISO format"""
        # Common date selectors
        date_selectors = [
            soup.find('time'),
            soup.find(attrs={'datetime': True}),
            soup.find(['span', 'div'], class_=re.compile(r'date|time|posted', re.IGNORECASE)),
        ]
        
        for element in date_selectors:
            if not element:
                continue
            
            # Try datetime attribute first
            date_str = element.get('datetime')
            if date_str:
                try:
                    # Parse ISO format
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    return dt.date().isoformat()
                except ValueError:
                    pass
            
            # Try text content
            date_text = element.get_text(strip=True)
            parsed_date = self._parse_date_text(date_text)
            if parsed_date:
                return parsed_date
        
        return None
    
    def _parse_date_text(self, date_text: str) -> Optional[str]:
        """Parse date from text using multiple format patterns"""
        for pattern in config.DATE_PATTERNS:
            try:
                dt = datetime.strptime(date_text, pattern)
                return dt.date().isoformat()
            except ValueError:
                continue
        
        # Handle relative dates (e.g., "Il y a 3 jours", "3 days ago")
        relative_patterns = [
            (r'(\d+)\s*(jour|day)s?', 'days'),
            (r'(\d+)\s*(heure|hour)s?', 'hours'),
            (r'(\d+)\s*(semaine|week)s?', 'weeks'),
            (r'(\d+)\s*(mois|month)s?', 'months'),
        ]
        
        for pattern, unit in relative_patterns:
            match = re.search(pattern, date_text, re.IGNORECASE)
            if match:
                # For relative dates, we'd need to calculate from current date
                # For now, return None (could be enhanced)
                return None
        
        return None
    
    def _extract_criteria(self, soup: BeautifulSoup) -> Dict:
        """
        Extract all listing criteria/features dynamically
        
        Common patterns:
        - Key-value tables (<table>, <dl>, or divs with label/value structure)
        - List items with icons and text
        - Data attributes
        """
        criteria = {}
        
        # Strategy 1: Definition lists <dl>
        dl = soup.find('dl')
        if dl:
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key = self._normalize_criteria_key(dt.get_text(strip=True))
                value = dd.get_text(strip=True)
                criteria[key] = value
        
        # Strategy 2: Tables
        tables = soup.find_all('table', class_=re.compile(r'detail|spec|feature|criteria', re.IGNORECASE))
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = self._normalize_criteria_key(cells[0].get_text(strip=True))
                    value = cells[1].get_text(strip=True)
                    criteria[key] = value
        
        # Strategy 3: Divs with label/value pattern
        feature_containers = soup.find_all('div', class_=re.compile(r'feature|spec|detail|criteria', re.IGNORECASE))
        for container in feature_containers:
            labels = container.find_all(['span', 'div', 'p'], class_=re.compile(r'label|key|name', re.IGNORECASE))
            values = container.find_all(['span', 'div', 'p'], class_=re.compile(r'value|data', re.IGNORECASE))
            
            for label, value in zip(labels, values):
                key = self._normalize_criteria_key(label.get_text(strip=True))
                val = value.get_text(strip=True)
                criteria[key] = val
        
        # Extract and normalize common numeric fields
        criteria = self._normalize_criteria_values(criteria)
        
        return criteria
    
    def _normalize_criteria_key(self, key: str) -> str:
        """Normalize criteria keys to consistent format"""
        # Remove special characters, convert to lowercase, replace spaces with underscores
        normalized = re.sub(r'[^\w\s]', '', key.lower())
        normalized = re.sub(r'\s+', '_', normalized)
        
        # Map to standard keys
        key_mappings = {
            'superficie': 'surface',
            'surface_habitable': 'surface',
            'surface_area': 'surface',
            'chambres': 'bedrooms',
            'nombre_de_chambres': 'bedrooms',
            'pieces': 'rooms',
            'nombre_de_pieces': 'rooms',
            'salle_de_bain': 'bathrooms',
            'salles_de_bain': 'bathrooms',
            'etage': 'floor',
            'meuble': 'furnished',
        }
        
        return key_mappings.get(normalized, normalized)
    
    def _normalize_criteria_values(self, criteria: Dict) -> Dict:
        """Normalize criteria values (extract numbers, booleans, etc.)"""
        normalized = {}
        
        for key, value in criteria.items():
            # Try to extract numeric value
            numbers = re.findall(r'\d+\.?\d*', value)
            if numbers and key in ['surface', 'rooms', 'bedrooms', 'bathrooms', 'floor']:
                normalized[key] = float(numbers[0])
            # Boolean fields
            elif key in ['furnished', 'garage', 'elevator', 'pool', 'garden', 'balcony']:
                normalized[key] = self._parse_boolean(value)
            else:
                normalized[key] = value
        
        return normalized
    
    def _parse_boolean(self, value: str) -> bool:
        """Parse boolean value from text"""
        value_lower = value.lower()
        true_values = ['oui', 'yes', 'true', '1', 'disponible', 'available']
        return any(tv in value_lower for tv in true_values)
    
    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """Extract all listing image URLs"""
        image_urls = []
        
        # Strategy 1: Find gallery or carousel containers
        gallery = soup.find(['div', 'section'], class_=re.compile(r'gallery|carousel|slider|images', re.IGNORECASE))
        
        if gallery:
            images = gallery.find_all('img')
        else:
            # Strategy 2: All images in main content area
            # Exclude header/footer images
            main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|detail|listing', re.IGNORECASE))
            images = main_content.find_all('img') if main_content else soup.find_all('img')
        
        for img in images:
            # Get highest quality source
            src = img.get('data-src') or img.get('src')  # Lazy-loaded images often use data-src
            
            if not src:
                continue
            
            # Skip tiny images (icons, logos)
            width = img.get('width')
            if width and int(width) < 100:
                continue
            
            # Convert to absolute URL
            full_url = urljoin(config.BASE_URL, src)
            
            # Avoid duplicates
            if full_url not in image_urls:
                image_urls.append(full_url)
        
        # Limit images if configured
        if config.MAX_IMAGES_PER_LISTING:
            image_urls = image_urls[:config.MAX_IMAGES_PER_LISTING]
        
        return image_urls
    
    def _validate_listing(self, data: Dict) -> bool:
        """Validate that listing has minimum required fields"""
        for field in config.MIN_REQUIRED_FIELDS:
            if field not in data or not data[field] or data[field] == 'N/A':
                logger.debug(f"Validation failed: missing or empty field '{field}'")
                return False
        return True
    
    def scrape_all(self, max_pages: Optional[int] = None) -> List[Dict]:
        """
        Scrape all listings across multiple pages
        
        Args:
            max_pages: Maximum number of pages to scrape (None for unlimited)
            
        Returns:
            List of all scraped listing dictionaries
        """
        all_listings = []
        page = 1
        max_pages = max_pages or config.MAX_PAGES
        
        # Use a set of listing IDs for much faster duplicate checking O(1)
        # This prevents the scraper from slowing down as the list grows
        scraped_ids = set()
        
        logger.info(f"Starting full scrape of Tayara.tn immobilier listings (Sample size: {config.SAMPLE_SIZE})")
        
        try:
            while True:
                # Check if we've reached page limit
                if max_pages and page > max_pages:
                    logger.info(f"Reached maximum page limit: {max_pages}")
                    break
                
                # Check sample size limit (for testing)
                if config.SAMPLE_SIZE and len(all_listings) >= config.SAMPLE_SIZE:
                    logger.info(f"Reached sample size limit: {config.SAMPLE_SIZE}")
                    break
                
                # Get listing links from current page
                logger.info(f"Scraping page {page}...")
                listing_links, has_next = self.get_listing_links(page)
                
                if not listing_links:
                    logger.warning(f"No listings found on page {page}")
                    break
                
                # Scrape each listing
                for idx, link in enumerate(listing_links, 1):
                    # Periodically save progress to prevent data loss on crashes (every 50 listings)
                    if len(all_listings) > 0 and len(all_listings) % 50 == 0 and not config.DRY_RUN:
                        self._save_checkpoint(all_listings)
                    
                    logger.info(f"Page {page}, Listing {idx}/{len(listing_links)} (Total unique: {len(all_listings)}): {link}")
                    
                    listing_data = self.parse_listing(link)
                    if listing_data:
                        lid = listing_data.get('listing_id')
                        lurl = listing_data.get('listing_url')
                        
                        # Use set for O(1) duplicate check
                        if lid not in scraped_ids and lurl not in scraped_ids:
                            all_listings.append(listing_data)
                            if lid: scraped_ids.add(lid)
                            if lurl: scraped_ids.add(lurl)
                        else:
                            logger.info(f"Skipping duplicate listing: {lid or lurl}")
                    
                    # Check sample size again (only count unique listings)
                    if config.SAMPLE_SIZE and len(all_listings) >= config.SAMPLE_SIZE:
                        break
                
                # Move to next page if available
                if not has_next:
                    logger.info("No more pages available")
                    break
                
                page += 1
                
        except (KeyboardInterrupt, Exception) as e:
            if isinstance(e, KeyboardInterrupt):
                logger.warning("Scraping process interrupted. Returning partial results.")
            else:
                logger.error(f"Error during scrape at page {page}, listing {idx}: {str(e)}")
            # Fall through to return whatever we managed to collect
        
        logger.info(f"Scraping complete: {len(all_listings)} listings collected, {self.errors_encountered} errors")
        return all_listings

    def _save_checkpoint(self, listings: List[Dict]):
        """Save a periodic checkpoint of scraped data"""
        try:
            checkpoint_path = config.PROCESSED_DATA_DIR / "latest_scrape_checkpoint.json"
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(listings, f, indent=4, ensure_ascii=False)
            logger.debug(f"Saved checkpoint of {len(listings)} listings to {checkpoint_path}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
