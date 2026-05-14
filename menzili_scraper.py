"""
Core web scraping module for Menzili.tn real estate listings.

The output schema matches the Tayara scraper so the existing exporter,
quality checks, and database pipeline can be reused.
"""

import hashlib
import json
import logging
import random
import re
import time
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config


logger = logging.getLogger(__name__)


class MenziliScraper:
    """
    Scraper for Menzili.tn real estate listings.

    It extracts:
    - listing links from search result pages
    - title, price, location, reference/date, description
    - property details, options, and image URLs from detail pages
    """

    def __init__(self):
        """Initialize the scraper with session and configuration."""
        source_config = config.SOURCE_CONFIGS['menzili']
        self.base_url = source_config['base_url']
        self.immobilier_url = source_config['immobilier_url']
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        self.listings_scraped = 0
        self.errors_encountered = 0

        logger.info("Menzili scraper initialized")

    def _make_request(self, url: str, retry_count: int = 0) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and exponential backoff."""
        try:
            delay = random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)
            time.sleep(delay)

            logger.debug(f"Requesting URL: {url}")
            response = self.session.get(
                url,
                timeout=config.REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                logger.warning(f"Unexpected content type: {content_type}")

            return response

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {str(e)}")

            if retry_count < config.MAX_RETRIES:
                backoff_time = config.BACKOFF_FACTOR ** retry_count
                logger.info(
                    f"Retrying in {backoff_time} seconds... "
                    f"(Attempt {retry_count + 1}/{config.MAX_RETRIES})"
                )
                time.sleep(backoff_time)
                return self._make_request(url, retry_count + 1)

            logger.error(f"Max retries reached for {url}")
            self.errors_encountered += 1
            return None

    def _page_url(self, page: int) -> str:
        """Build a Menzili result page URL."""
        if page <= 1:
            return self.immobilier_url
        return f"{self.immobilier_url}?l=0&page={page}&tri=1"

    def get_listing_links(self, page: int = 1) -> Tuple[List[str], bool]:
        """
        Extract listing URLs from a Menzili search results page.

        Menzili listing URLs currently use /annonce/<slug>-<id>.
        """
        url = self._page_url(page)
        response = self._make_request(url)
        if not response:
            return [], False

        soup = BeautifulSoup(response.content, 'html.parser')

        if config.SAVE_HTML_SNAPSHOTS:
            snapshot_path = config.RAW_DATA_DIR / f"menzili_page_{page}.html"
            snapshot_path.write_text(response.text, encoding='utf-8')
            logger.debug(f"Saved HTML snapshot: {snapshot_path}")

        listing_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/annonce/' not in href:
                continue

            full_url = urljoin(self.base_url, href).split('#', 1)[0]
            if full_url not in listing_links:
                listing_links.append(full_url)

        next_page = page + 1
        has_next_page = bool(
            soup.find('a', href=re.compile(rf'page={next_page}(&|$)'))
            or soup.find('a', string=re.compile(r'^\s*>\s*$'))
            or soup.find('a', string=re.compile(r'^\s*>>\s*$'))
        )

        if len(listing_links) < 3:
            has_next_page = False

        logger.info(
            f"Menzili page {page}: Found {len(listing_links)} listings, "
            f"has_next={has_next_page}"
        )

        return listing_links, has_next_page

    def parse_listing(self, url: str) -> Optional[Dict]:
        """Parse a single Menzili listing page and return normalized data."""
        response = self._make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        lines = self._text_lines(soup)
        title = self._extract_title(soup)
        price_data = self._extract_price(soup)
        location_data = self._extract_location(lines, title)
        criteria = self._extract_details(soup)
        options = self._extract_options(lines)

        if options:
            criteria['options'] = options
            criteria.update(self._option_booleans(options))

        if price_data.get('price_period'):
            criteria['price_period'] = price_data.pop('price_period')

        data = {
            'source': 'menzili.tn',
            'listing_url': url,
            'listing_id': self._extract_listing_id(url, soup),
            'title': title,
            'category': self._extract_category(soup, url, title),
            'transaction_type': self._extract_transaction_type(soup, url, title),
            'description': self._extract_description(lines),
            'date_posted': self._extract_date(soup),
            'criteria': criteria,
            'image_urls': self._extract_images(soup, title),
            'scraped_at': datetime.now().isoformat(),
        }
        data.update(price_data)
        data.update(location_data)
        data['image_count'] = len(data['image_urls'])

        for key in ['surface', 'rooms', 'bedrooms', 'bathrooms', 'floor', 'furnished']:
            if key in criteria:
                data[key] = criteria[key]

        if config.ENABLE_DATA_VALIDATION and not self._validate_listing(data):
            logger.warning(f"Listing failed validation: {url}")
            return None

        self.listings_scraped += 1
        logger.info(
            f"Successfully parsed Menzili listing {self.listings_scraped}: "
            f"{data.get('title', 'N/A')[:50]}"
        )
        return data

    def _extract_listing_id(self, url: str, soup: BeautifulSoup) -> str:
        """Extract the Menzili reference ID or generate a stable fallback."""
        id_from_url = re.search(r'-(\d+)(?:/?$)', url)
        if id_from_url:
            return id_from_url.group(1)

        text = soup.get_text(" ", strip=True)
        ref_match = re.search(r'R[\u00e8e]f\s*:\s*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
        if ref_match:
            return ref_match.group(1)

        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"menzili_hash_{url_hash}"

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract listing title."""
        h1 = soup.find('h1')
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            return meta_title['content'].strip()

        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            return re.sub(r'\s*[-|]\s*Menzili.*$', '', title, flags=re.IGNORECASE)

        return "N/A"

    def _extract_price(self, soup: BeautifulSoup) -> Dict:
        """Extract price, currency, and optional period."""
        text = soup.get_text(" ", strip=True)
        result = {
            'price_raw': 'N/A',
            'price_numeric': None,
            'currency': 'TND',
        }

        price_match = re.search(
            r'(\d[\d\s.,]*)\s*(DT|TND)(?:\s*/\s*([A-Za-z]+))?',
            text,
            re.IGNORECASE,
        )
        if not price_match:
            return result

        amount, currency, period = price_match.groups()
        result['price_raw'] = price_match.group(0).strip()
        result['price_numeric'] = self._parse_number(amount)
        result['currency'] = config.CURRENCY_SYMBOLS.get(currency, currency.upper())
        if period:
            result['price_period'] = period.lower()

        return result

    def _extract_category(self, soup: BeautifulSoup, url: str, title: str) -> str:
        """Extract and normalize listing category."""
        breadcrumb_candidates = [
            link.get_text(strip=True).lower()
            for link in soup.find_all('a')
            if link.get_text(strip=True)
        ]

        for candidate in breadcrumb_candidates:
            normalized = self._normalize_category(candidate)
            if normalized != candidate:
                return normalized

        haystack = f"{url} {title}".lower()
        for key, value in config.CATEGORY_MAPPINGS.items():
            if key in haystack:
                return value

        return "N/A"

    def _extract_transaction_type(self, soup: BeautifulSoup, url: str, title: str) -> Optional[str]:
        """Extract sale/rent classification."""
        haystack = f"{url} {title} {soup.get_text(' ', strip=True)[:500]}".lower()
        if re.search(r'\b(louer|location|a-louer|louer)\b', haystack):
            return 'rent'
        if re.search(r'\b(vendre|vente|a-vendre|acheter)\b', haystack):
            return 'sale'
        return None

    def _extract_location(self, lines: List[str], title: str) -> Dict:
        """Extract location from the line immediately below the title."""
        result = {
            'location_raw': 'N/A',
            'city': None,
            'governorate': None,
            'neighborhood': None,
        }

        try:
            start_index = lines.index(title)
        except ValueError:
            start_index = 0

        for line in lines[start_index + 1:start_index + 10]:
            if ',' not in line or self._looks_like_price(line):
                continue
            if self._normalized(line) in ['premium', 'description']:
                continue

            result['location_raw'] = line
            parts = [part.strip() for part in line.split(',') if part.strip()]
            if len(parts) >= 3:
                result['neighborhood'] = parts[0]
                result['city'] = parts[-2]
                result['governorate'] = parts[-1]
            elif len(parts) == 2:
                result['city'] = parts[0]
                result['governorate'] = parts[1]
            elif parts:
                result['city'] = parts[0]
            break

        return result

    def _extract_description(self, lines: List[str]) -> str:
        """Extract description section text."""
        description_lines = self._extract_section(
            lines,
            start_labels=['description'],
            end_labels=['details de bien', 'options', 'localisation'],
        )
        return '\n'.join(description_lines).strip() or "N/A"

    def _extract_details(self, soup: BeautifulSoup) -> Dict:
        """Extract property detail fields into criteria."""
        text = soup.get_text(" ", strip=True)
        criteria = {}

        patterns = {
            'bedrooms': r'Chambres?\s*:\s*(\d+\+?)',
            'bathrooms': r'Salles?\s+de\s+bain\s*:\s*(\d+\+?)',
            'rooms': r'Pi[\u00e8e\u00e9]ces?\s*(?:\(Totale\))?\s*:\s*(\d+\+?)',
            'surface': r'Surf\s+habitable\s*:\s*([\d\s.,]+)\s*m(?:2|\u00b2)?',
            'surface_land': r'Surf\s+terrain\s*:\s*([\d\s.,]+)\s*m(?:2|\u00b2)?',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue

            value = match.group(1)
            criteria[key] = self._parse_count(value) if key in ['bedrooms', 'bathrooms', 'rooms'] else self._parse_number(value)

        return criteria

    def _extract_options(self, lines: List[str]) -> List[str]:
        """Extract option labels from the options section."""
        option_lines = self._extract_section(
            lines,
            start_labels=['options'],
            end_labels=['localisation', 'contacter lannonceur'],
        )
        option_text = ' '.join(option_lines)
        if not option_text:
            return []

        known_options = [
            'Acces internet',
            'Interphone',
            'Climatisation',
            'Parabole / TV',
            'Terrasses',
            'Piscine',
            'Meuble',
            'Cuisine equipe',
            'Garage',
            'Jardin',
            'Place de parc',
            'Ascenseur',
            'Balcon',
        ]

        normalized_option_text = self._normalized(option_text)
        found_options = []
        for option in known_options:
            if self._normalized(option) in normalized_option_text:
                found_options.append(option)

        return found_options or [option_text.strip()]

    def _option_booleans(self, options: List[str]) -> Dict:
        """Map Menzili options to normalized boolean criteria."""
        normalized_options = self._normalized(' '.join(options))
        return {
            'garage': 'garage' in normalized_options,
            'garden': 'jardin' in normalized_options,
            'pool': 'piscine' in normalized_options,
            'furnished': 'meuble' in normalized_options,
            'terrace': 'terrasse' in normalized_options,
            'elevator': 'ascenseur' in normalized_options,
            'balcony': 'balcon' in normalized_options,
            'parking': 'place de parc' in normalized_options,
            'air_conditioning': 'climatisation' in normalized_options,
            'internet': 'acces internet' in normalized_options,
        }

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract posted date from the Menzili reference line."""
        text = soup.get_text(" ", strip=True)
        match = re.search(
            r'D[\u00e9e]pos[\u00e9e]e?\s+le\s*:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})',
            text,
            re.IGNORECASE,
        )
        if not match:
            return None

        date_text = match.group(1)
        for pattern in ["%d/%m/%y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_text, pattern).date().isoformat()
            except ValueError:
                continue

        return None

    def _extract_images(self, soup: BeautifulSoup, title: str) -> List[str]:
        """Extract listing image URLs."""
        image_urls = []
        title_normalized = self._normalized(title)

        for img in soup.find_all('img'):
            src = (
                img.get('data-src')
                or img.get('data-original')
                or img.get('data-lazy')
                or img.get('src')
            )
            if not src:
                continue

            src_lower = src.lower()
            if any(token in src_lower for token in ['logo', 'sprite', 'facebook', 'twitter']):
                continue

            width = img.get('width')
            if width and width.isdigit() and int(width) < 100:
                continue

            alt = img.get('alt', '')
            alt_normalized = self._normalized(alt)
            if title_normalized != 'na' and alt_normalized:
                if title_normalized not in alt_normalized:
                    continue

            full_url = urljoin(self.base_url, src)
            if full_url not in image_urls:
                image_urls.append(full_url)

        if config.MAX_IMAGES_PER_LISTING:
            image_urls = image_urls[:config.MAX_IMAGES_PER_LISTING]

        return image_urls

    def _extract_section(self, lines: List[str], start_labels: List[str], end_labels: List[str]) -> List[str]:
        """Extract text lines between normalized section labels."""
        normalized_starts = {self._normalized(label) for label in start_labels}
        normalized_ends = {self._normalized(label) for label in end_labels}

        start_index = None
        for idx, line in enumerate(lines):
            if self._normalized(line) in normalized_starts:
                start_index = idx + 1
                break

        if start_index is None:
            return []

        section_lines = []
        for line in lines[start_index:]:
            normalized_line = self._normalized(line)
            if normalized_line in normalized_ends or normalized_line == '* * *':
                break
            section_lines.append(line)

        return section_lines

    def _validate_listing(self, data: Dict) -> bool:
        """Validate that listing has minimum required fields."""
        for field in config.MIN_REQUIRED_FIELDS:
            if field == 'price':
                has_price = (
                    data.get('price_numeric') not in [None, '', 'N/A']
                    or data.get('price_raw') not in [None, '', 'N/A']
                )
                if has_price:
                    continue

            if field not in data or not data[field] or data[field] == 'N/A':
                logger.debug(f"Validation failed: missing or empty field '{field}'")
                return False
        return True

    def scrape_all(self, max_pages: Optional[int] = None) -> List[Dict]:
        """Scrape all listings across multiple Menzili result pages."""
        all_listings = []
        page = 1
        max_pages = max_pages or config.MAX_PAGES
        scraped_ids = set()
        listing_index = 0

        logger.info(
            f"Starting full scrape of Menzili.tn immobilier listings "
            f"(Sample size: {config.SAMPLE_SIZE})"
        )

        try:
            while True:
                if max_pages and page > max_pages:
                    logger.info(f"Reached maximum page limit: {max_pages}")
                    break

                if config.SAMPLE_SIZE and len(all_listings) >= config.SAMPLE_SIZE:
                    logger.info(f"Reached sample size limit: {config.SAMPLE_SIZE}")
                    break

                logger.info(f"Scraping Menzili page {page}...")
                listing_links, has_next = self.get_listing_links(page)

                if not listing_links:
                    logger.warning(f"No listings found on Menzili page {page}")
                    break

                for listing_index, link in enumerate(listing_links, 1):
                    if len(all_listings) > 0 and len(all_listings) % 50 == 0 and not config.DRY_RUN:
                        self._save_checkpoint(all_listings)

                    logger.info(
                        f"Page {page}, Listing {listing_index}/{len(listing_links)} "
                        f"(Total unique: {len(all_listings)}): {link}"
                    )

                    listing_data = self.parse_listing(link)
                    if listing_data:
                        listing_id = listing_data.get('listing_id')
                        listing_url = listing_data.get('listing_url')
                        dedupe_key = listing_id or listing_url

                        if dedupe_key not in scraped_ids and listing_url not in scraped_ids:
                            all_listings.append(listing_data)
                            if listing_id:
                                scraped_ids.add(listing_id)
                            if listing_url:
                                scraped_ids.add(listing_url)
                        else:
                            logger.info(f"Skipping duplicate listing: {dedupe_key}")

                    if config.SAMPLE_SIZE and len(all_listings) >= config.SAMPLE_SIZE:
                        break

                if not has_next:
                    logger.info("No more Menzili pages available")
                    break

                page += 1

        except (KeyboardInterrupt, Exception) as e:
            if isinstance(e, KeyboardInterrupt):
                logger.warning("Scraping process interrupted. Returning partial results.")
            else:
                logger.error(
                    f"Error during Menzili scrape at page {page}, "
                    f"listing {listing_index}: {str(e)}"
                )

        logger.info(
            f"Menzili scraping complete: {len(all_listings)} listings collected, "
            f"{self.errors_encountered} errors"
        )
        return all_listings

    def _save_checkpoint(self, listings: List[Dict]):
        """Save a periodic checkpoint of scraped data."""
        try:
            checkpoint_path = config.PROCESSED_DATA_DIR / "latest_menzili_scrape_checkpoint.json"
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(listings, f, indent=4, ensure_ascii=False)
            logger.debug(f"Saved checkpoint of {len(listings)} listings to {checkpoint_path}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def _text_lines(self, soup: BeautifulSoup) -> List[str]:
        """Return non-empty visible text lines."""
        return [
            line.strip()
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        ]

    def _normalize_category(self, category_text: str) -> str:
        """Normalize category to standard values."""
        category_lower = category_text.lower().strip()
        return config.CATEGORY_MAPPINGS.get(category_lower, category_text)

    def _parse_number(self, value: str) -> Optional[float]:
        """Parse a number containing spaces, commas, or dots."""
        if value is None:
            return None

        cleaned = value.replace(' ', '').replace(',', '.')
        cleaned = re.sub(r'[^\d.]', '', cleaned)
        if not cleaned:
            return None

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _parse_count(self, value: str) -> Optional[float]:
        """Parse integer-like count values, including values such as 10+."""
        if value is None:
            return None

        match = re.search(r'\d+', value)
        if not match:
            return None
        return float(match.group(0))

    def _looks_like_price(self, value: str) -> bool:
        """Return True if a line looks like a price line."""
        return bool(re.search(r'\d[\d\s.,]*\s*(DT|TND|EUR|\u20ac|\$)', value, re.IGNORECASE))

    def _normalized(self, value: str) -> str:
        """Normalize strings for accent-insensitive matching."""
        normalized = unicodedata.normalize('NFKD', value or '')
        ascii_value = normalized.encode('ascii', 'ignore').decode('ascii')
        ascii_value = re.sub(r'[^\w\s/*+>-]', '', ascii_value.lower())
        ascii_value = re.sub(r'\s+', ' ', ascii_value)
        return ascii_value.strip()
