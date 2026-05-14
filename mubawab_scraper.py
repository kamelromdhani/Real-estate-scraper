"""
Core web scraping module for Mubawab.tn real estate listings.

Mubawab search pages are built from a transaction, property type, and
optionally a location path. The output schema matches the other scrapers so
the shared exporter, validation, and date filtering can be reused.
"""

import hashlib
import json
import logging
import random
import re
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config


logger = logging.getLogger(__name__)


class MubawabScraper:
    """Scraper for Mubawab.tn listing result pages and detail pages."""

    PROPERTY_SLUGS = {
        'logement': {
            'sale': 'appartements-a-vendre',
            'rent': 'appartements-a-louer',
            'category': 'apartment',
        },
        'apartment': {
            'sale': 'appartements-a-vendre',
            'rent': 'appartements-a-louer',
            'category': 'apartment',
        },
        'appartement': {
            'sale': 'appartements-a-vendre',
            'rent': 'appartements-a-louer',
            'category': 'apartment',
        },
        'terrain': {
            'sale': 'terrains-a-vendre',
            'rent': 'terrains-a-louer',
            'category': 'land',
        },
        'land': {
            'sale': 'terrains-a-vendre',
            'rent': 'terrains-a-louer',
            'category': 'land',
        },
        'house': {
            'sale': 'maisons-a-vendre',
            'rent': 'maisons-a-louer',
            'category': 'house',
        },
        'maison': {
            'sale': 'maisons-a-vendre',
            'rent': 'maisons-a-louer',
            'category': 'house',
        },
        'villa': {
            'sale': 'villas-et-maisons-de-luxe-a-vendre',
            'rent': 'villas-et-maisons-de-luxe-a-louer',
            'category': 'villa',
        },
        'commercial': {
            'sale': 'locaux-a-vendre',
            'rent': 'locaux-a-louer',
            'category': 'commercial',
        },
        'local': {
            'sale': 'locaux-a-vendre',
            'rent': 'locaux-a-louer',
            'category': 'commercial',
        },
        'office': {
            'sale': 'bureaux-a-vendre',
            'rent': 'bureaux-a-louer',
            'category': 'office',
        },
        'bureau': {
            'sale': 'bureaux-a-vendre',
            'rent': 'bureaux-a-louer',
            'category': 'office',
        },
    }

    TRANSACTION_MAPPINGS = {
        'sale': 'sale',
        'vente': 'sale',
        'vendre': 'sale',
        'buy': 'sale',
        'achat': 'sale',
        'rent': 'rent',
        'location': 'rent',
        'louer': 'rent',
    }

    OPTION_MAPPINGS = {
        'garage': ['garage'],
        'garden': ['jardin'],
        'terrace': ['terrasse'],
        'elevator': ['ascenseur'],
        'pool': ['piscine'],
        'furnished': ['meuble'],
        'concierge': ['concierge'],
        'air_conditioning': ['climatisation'],
        'central_heating': ['chauffage central'],
        'security': ['securite'],
        'double_glazing': ['double vitrage'],
        'equipped_kitchen': ['cuisine equipee'],
        'sea_view': ['vue sur mer'],
        'mountain_view': ['vue sur les montagnes'],
        'internet': ['internet'],
    }

    DETAIL_LABELS = {
        'type de bien': 'property_type',
        'type de terrain': 'land_type',
        'livraison': 'delivery',
        'statut du terrain': 'land_status',
        'etat': 'condition',
        'standing': 'standing',
        'orientation': 'orientation',
        'type de sol': 'flooring',
        'type du sol': 'flooring',
        'etage du bien': 'floor',
    }

    def __init__(
        self,
        transaction: str = None,
        property_type: str = None,
        location: str = None,
        location_level: str = None,
        search_url: str = None,
    ):
        """Initialize the scraper with search settings."""
        source_config = config.SOURCE_CONFIGS['mubawab']
        self.base_url = source_config['base_url']
        self.transaction = self._normalize_transaction(transaction or config.MUBAWAB_TRANSACTION)
        self.property_type = self._normalize_property_type(property_type or config.MUBAWAB_PROPERTY_TYPE)
        self.location = location if location is not None else config.MUBAWAB_LOCATION
        self.location_level = location_level or config.MUBAWAB_LOCATION_LEVEL
        self.search_url = search_url or config.MUBAWAB_SEARCH_URL
        self.category = self.PROPERTY_SLUGS[self.property_type]['category']
        self.start_url = self._build_search_url()

        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        self.listings_scraped = 0
        self.errors_encountered = 0

        logger.info(
            "Mubawab scraper initialized "
            f"(transaction={self.transaction}, property_type={self.property_type}, "
            f"location={self.location or 'all'}, url={self.start_url})"
        )

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

    def _build_search_url(self) -> str:
        """Build a Mubawab search URL from configured dimensions."""
        if self.search_url:
            return urljoin(self.base_url, self.search_url)

        listing_slug = self.PROPERTY_SLUGS[self.property_type][self.transaction]
        if not self.location or self.location_level == 'sc':
            return f"{self.base_url}/fr/sc/{listing_slug}"

        location_slug = self._slug_path(self.location)
        return f"{self.base_url}/fr/{self.location_level}/{location_slug}/{listing_slug}"

    def _page_url(self, page: int) -> str:
        """Build a page URL. Mubawab uses :p:N on many result pages."""
        if page <= 1:
            return self.start_url

        if re.search(r':p:\d+/?$', self.start_url):
            return re.sub(r':p:\d+/?$', f":p:{page}", self.start_url)

        return f"{self.start_url}:p:{page}"

    def get_listing_links(self, page: int = 1) -> Tuple[List[str], bool]:
        """Extract listing URLs from a Mubawab search page."""
        url = self._page_url(page)
        response = self._make_request(url)
        if not response:
            return [], False

        soup = BeautifulSoup(response.content, 'html.parser')

        if config.SAVE_HTML_SNAPSHOTS:
            snapshot_path = config.RAW_DATA_DIR / f"mubawab_page_{page}.html"
            snapshot_path.write_text(response.text, encoding='utf-8')
            logger.debug(f"Saved HTML snapshot: {snapshot_path}")

        listing_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if not re.search(r'/(?:fr/)?(?:a|pa)/\d+/', href):
                continue

            full_url = urljoin(self.base_url, href).split('#', 1)[0]
            if full_url not in listing_links:
                listing_links.append(full_url)

        next_page = page + 1
        has_next_page = bool(
            soup.find('a', href=re.compile(rf':p:{next_page}(?:/|$)'))
            or soup.find('a', string=re.compile(r'^\s*(suivant|next|>|>>)\s*$', re.IGNORECASE))
        )

        logger.info(
            f"Mubawab page {page}: Found {len(listing_links)} listings, "
            f"has_next={has_next_page}"
        )
        return listing_links, has_next_page

    def parse_listing(self, url: str) -> Optional[Dict]:
        """Parse a single Mubawab listing page and return normalized data."""
        response = self._make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        lines = self._text_lines(soup)
        title = self._extract_title(soup)
        criteria = self._extract_criteria(lines)
        criteria.update(self._extract_general_characteristics(lines))
        criteria.update(self._option_booleans(lines))

        data = {
            'source': 'mubawab.tn',
            'listing_url': url,
            'listing_id': self._extract_listing_id(url),
            'title': title,
            'category': self.category,
            'transaction_type': self.transaction,
            'location_raw': self._extract_location_raw(lines, title),
            'description': self._extract_description(lines, title),
            'date_posted': self._extract_date(lines),
            'criteria': criteria,
            'image_urls': self._extract_images(soup, title),
            'scraped_at': datetime.now().isoformat(),
        }
        data.update(self._extract_price(lines))
        data.update(self._parse_location(data['location_raw']))
        data['image_count'] = len(data['image_urls'])

        for key in ['surface', 'rooms', 'bedrooms', 'bathrooms', 'floor', 'furnished']:
            if key in criteria:
                data[key] = criteria[key]

        if config.ENABLE_DATA_VALIDATION and not self._validate_listing(data):
            logger.warning(f"Listing failed validation: {url}")
            return None

        self.listings_scraped += 1
        logger.info(
            f"Successfully parsed Mubawab listing {self.listings_scraped}: "
            f"{data.get('title', 'N/A')[:50]}"
        )
        return data

    def _extract_listing_id(self, url: str) -> str:
        """Extract listing ID from Mubawab detail URL."""
        match = re.search(r'/(?:a|pa)/(\d+)/', url)
        if match:
            return match.group(1)

        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"mubawab_hash_{url_hash}"

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
            return re.sub(r'\s*[-|]\s*Mubawab.*$', '', title, flags=re.IGNORECASE)

        return "N/A"

    def _extract_price(self, lines: List[str]) -> Dict:
        """Extract price, currency, and raw price string."""
        result = {
            'price_raw': 'N/A',
            'price_numeric': None,
            'currency': 'TND',
        }

        for line in lines[:80]:
            normalized_line = self._normalized(line)
            if 'prix a consulter' in normalized_line:
                result['price_raw'] = 'Prix a consulter'
                return result

            match = re.search(
                r'((?:a partir de\s*)?\d[\d\s.,]*)\s*(TND|DT|EUR|USD|\$|euro)',
                self._ascii_fold(line),
                re.IGNORECASE,
            )
            if not match:
                continue

            result['price_raw'] = line.strip()
            result['price_numeric'] = self._parse_number(match.group(1))
            result['currency'] = self._normalize_currency(match.group(2))
            return result

        return result

    def _extract_location_raw(self, lines: List[str], title: str) -> str:
        """Extract the most likely location line."""
        candidates = []

        try:
            title_index = lines.index(title)
        except ValueError:
            title_index = 0

        search_ranges = [
            lines[title_index + 1:title_index + 20],
            lines[:80],
        ]

        for search_range in search_ranges:
            for idx, line in enumerate(search_range):
                next_line = search_range[idx + 1] if idx + 1 < len(search_range) else ''
                candidate_line = line
                if self._normalized(line).endswith(' a') and next_line:
                    candidate_line = f"{line} {next_line}"

                normalized = self._normalized(line)
                if not line or len(line) > 80:
                    continue
                if self._looks_like_metric(line) or self._looks_like_price(line):
                    continue
                if normalized in [
                    'favori',
                    'partager',
                    'contacter',
                    'demander le prix',
                    'voir la carte',
                ]:
                    continue
                if ',' in candidate_line or re.search(r'\s[aà]\s', candidate_line, flags=re.IGNORECASE):
                    candidates.append(candidate_line)

            if candidates:
                break

        return candidates[0] if candidates else "N/A"

    def _parse_location(self, location_raw: str) -> Dict:
        """Parse raw location into city/governorate/neighborhood."""
        result = {
            'city': None,
            'governorate': None,
            'neighborhood': None,
        }

        if not location_raw or location_raw == 'N/A':
            return result

        parts = [part.strip() for part in location_raw.split(',') if part.strip()]
        if len(parts) >= 2:
            result['neighborhood'] = parts[0]
            result['city'] = parts[-1]
            result['governorate'] = parts[-1]
            return result

        match = re.match(r'(.+?)\s+[aà]\s+(.+)$', location_raw, flags=re.IGNORECASE)
        if match:
            result['neighborhood'] = match.group(1).strip()
            result['city'] = match.group(2).strip()
            result['governorate'] = result['city']
            return result

        result['city'] = location_raw.strip()
        return result

    def _extract_description(self, lines: List[str], title: str) -> str:
        """Extract description text."""
        try:
            start_index = lines.index(title) + 1
        except ValueError:
            start_index = 0

        description_lines = []
        skip_patterns = [
            r'^\d+(\.\d+)?\s*m',
            r'^\d+\s+pieces?',
            r'^\d+\s+ch',
            r'^\d+\s+salles?\s+de\s+bain',
            r'^prix a consulter$',
            r'^\d[\d\s.,]*\s*(tnd|dt|eur|usd)',
        ]

        for line in lines[start_index:start_index + 120]:
            normalized = self._normalized(line)
            if normalized in [
                'caracteristiques generales',
                'contacter lannonceur',
                'voir la carte',
                'favori',
                'partager',
            ]:
                break
            if any(re.search(pattern, normalized) for pattern in skip_patterns):
                continue
            if normalized in self._all_known_options():
                continue
            if len(line) >= 40:
                description_lines.append(line)

        return '\n'.join(description_lines).strip() or "N/A"

    def _extract_criteria(self, lines: List[str]) -> Dict:
        """Extract numeric criteria from listing text."""
        text = ' '.join(lines[:180])
        normalized_text = self._normalized(text)
        criteria = {}

        patterns = {
            'surface': r'(\d[\d\s.,]*)\s*m(?:2|²)?',
            'rooms': r'(\d+)\s+pieces?',
            'bedrooms': r'(\d+)\s+(?:chambres?|ch)\b',
            'bathrooms': r'(\d+)\s+salles?\s+de\s+bains?',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, normalized_text, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1)
            criteria[key] = self._parse_number(value)

        return criteria

    def _extract_general_characteristics(self, lines: List[str]) -> Dict:
        """Extract label/value pairs from the general characteristics section."""
        section = self._extract_section(
            lines,
            start_labels=['caracteristiques generales'],
            end_labels=['voir la carte', 'contacter lannonceur', 'contacter'],
        )
        if not section:
            return {}

        criteria = {}
        for idx, line in enumerate(section[:-1]):
            label = self._normalized(line)
            mapped_key = self.DETAIL_LABELS.get(label)
            if not mapped_key:
                continue
            value = section[idx + 1].strip()
            if value:
                criteria[mapped_key] = value

        return criteria

    def _option_booleans(self, lines: List[str]) -> Dict:
        """Map visible option labels to normalized boolean criteria."""
        normalized_lines = {self._normalized(line) for line in lines[:380]}
        booleans = {}

        for key, labels in self.OPTION_MAPPINGS.items():
            booleans[key] = any(label in normalized_lines for label in labels)

        return booleans

    def _extract_date(self, lines: List[str]) -> Optional[str]:
        """Extract an absolute or relative publication date when visible."""
        text = ' '.join(lines[:200])
        normalized_text = self._normalized(text)

        absolute_match = re.search(
            r'(?:publiee?|deposee?)\s+(?:le\s*)?:?\s*(\d{1,2}/\d{1,2}/\d{2,4})',
            normalized_text,
            re.IGNORECASE,
        )
        if absolute_match:
            return self._parse_french_date(absolute_match.group(1))

        relative_patterns = [
            (r'il y a\s+(\d+)\s+jours?', 'days'),
            (r'il y a\s+(\d+)\s+semaines?', 'weeks'),
            (r'il y a\s+(\d+)\s+mois', 'months'),
            (r'il y a\s+(\d+)\s+heures?', 'hours'),
        ]
        now = datetime.now()
        for pattern, unit in relative_patterns:
            match = re.search(pattern, normalized_text, re.IGNORECASE)
            if not match:
                continue

            value = int(match.group(1))
            if unit == 'days':
                return (now - timedelta(days=value)).date().isoformat()
            if unit == 'weeks':
                return (now - timedelta(weeks=value)).date().isoformat()
            if unit == 'months':
                return (now - timedelta(days=value * 30)).date().isoformat()
            if unit == 'hours':
                return now.date().isoformat()

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
            if alt and title_normalized not in self._normalized(alt):
                continue

            full_url = urljoin(self.base_url, src)
            if full_url not in image_urls:
                image_urls.append(full_url)

        if config.MAX_IMAGES_PER_LISTING:
            image_urls = image_urls[:config.MAX_IMAGES_PER_LISTING]

        return image_urls

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
        """Scrape all listings across Mubawab result pages."""
        all_listings = []
        page = 1
        max_pages = max_pages or config.MAX_PAGES
        scraped_ids = set()
        listing_index = 0

        logger.info(
            f"Starting full scrape of Mubawab.tn listings "
            f"(Sample size: {config.SAMPLE_SIZE}, start URL: {self.start_url})"
        )

        try:
            while True:
                if max_pages and page > max_pages:
                    logger.info(f"Reached maximum page limit: {max_pages}")
                    break

                if config.SAMPLE_SIZE and len(all_listings) >= config.SAMPLE_SIZE:
                    logger.info(f"Reached sample size limit: {config.SAMPLE_SIZE}")
                    break

                logger.info(f"Scraping Mubawab page {page}...")
                listing_links, has_next = self.get_listing_links(page)

                if not listing_links:
                    logger.warning(f"No listings found on Mubawab page {page}")
                    break

                new_listings_on_page = 0
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
                            new_listings_on_page += 1
                            if listing_id:
                                scraped_ids.add(listing_id)
                            if listing_url:
                                scraped_ids.add(listing_url)
                        else:
                            logger.info(f"Skipping duplicate listing: {dedupe_key}")

                    if config.SAMPLE_SIZE and len(all_listings) >= config.SAMPLE_SIZE:
                        break

                if not has_next:
                    logger.info("No more Mubawab pages available")
                    break

                if new_listings_on_page == 0:
                    logger.warning("No new listings on page; stopping to avoid repeated pages")
                    break

                page += 1

        except (KeyboardInterrupt, Exception) as e:
            if isinstance(e, KeyboardInterrupt):
                logger.warning("Scraping process interrupted. Returning partial results.")
            else:
                logger.error(
                    f"Error during Mubawab scrape at page {page}, "
                    f"listing {listing_index}: {str(e)}"
                )

        logger.info(
            f"Mubawab scraping complete: {len(all_listings)} listings collected, "
            f"{self.errors_encountered} errors"
        )
        return all_listings

    def _save_checkpoint(self, listings: List[Dict]):
        """Save a periodic checkpoint of scraped data."""
        try:
            checkpoint_path = config.PROCESSED_DATA_DIR / "latest_mubawab_scrape_checkpoint.json"
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(listings, f, indent=4, ensure_ascii=False)
            logger.debug(f"Saved checkpoint of {len(listings)} listings to {checkpoint_path}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def _normalize_transaction(self, value: str) -> str:
        """Normalize transaction CLI value."""
        normalized = self._normalized(value)
        if normalized not in self.TRANSACTION_MAPPINGS:
            valid = ', '.join(sorted(self.TRANSACTION_MAPPINGS))
            raise ValueError(f"Unsupported Mubawab transaction '{value}'. Expected one of: {valid}")
        return self.TRANSACTION_MAPPINGS[normalized]

    def _normalize_property_type(self, value: str) -> str:
        """Normalize property type CLI value."""
        normalized = self._normalized(value)
        if normalized not in self.PROPERTY_SLUGS:
            valid = ', '.join(sorted(self.PROPERTY_SLUGS))
            raise ValueError(f"Unsupported Mubawab property type '{value}'. Expected one of: {valid}")
        return normalized

    def _text_lines(self, soup: BeautifulSoup) -> List[str]:
        """Return non-empty visible text lines."""
        return [
            line.strip()
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        ]

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
            if normalized_line in normalized_ends:
                break
            section_lines.append(line)

        return section_lines

    def _parse_number(self, value: str) -> Optional[float]:
        """Parse a number containing spaces, commas, dots, or words."""
        if value is None:
            return None

        cleaned = self._ascii_fold(value)
        cleaned = re.sub(r'a partir de', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace(' ', '').replace(',', '.')
        cleaned = re.sub(r'[^\d.]', '', cleaned)
        if not cleaned:
            return None

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _normalize_currency(self, currency_str: str) -> str:
        """Normalize currency symbol to standard code."""
        currency = currency_str.upper()
        if currency in ['DT', 'TND']:
            return 'TND'
        if currency in ['EURO']:
            return 'EUR'
        return config.CURRENCY_SYMBOLS.get(currency_str, currency)

    def _parse_french_date(self, date_text: str) -> Optional[str]:
        """Parse French numeric dates."""
        for pattern in ["%d/%m/%y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_text, pattern).date().isoformat()
            except ValueError:
                continue
        return None

    def _looks_like_metric(self, value: str) -> bool:
        """Return True if a line looks like a metric/feature count."""
        normalized = self._normalized(value)
        return bool(
            re.search(r'\d+\s*m', normalized)
            or re.search(r'\d+\s+pieces?', normalized)
            or re.search(r'\d+\s+ch', normalized)
            or re.search(r'\d+\s+salles?\s+de\s+bain', normalized)
        )

    def _looks_like_price(self, value: str) -> bool:
        """Return True if a line looks like a price."""
        normalized = self._normalized(value)
        return bool('prix a consulter' in normalized or re.search(r'\d[\d\s.,]*\s*(tnd|dt|eur|usd)', normalized))

    def _all_known_options(self) -> set:
        """Return all normalized known option labels."""
        labels = set()
        for option_labels in self.OPTION_MAPPINGS.values():
            labels.update(option_labels)
        return labels

    def _slug_path(self, value: str) -> str:
        """Slugify a location path while preserving nested path separators."""
        segments = [segment for segment in str(value).split('/') if segment.strip()]
        return '/'.join(self._slugify(segment) for segment in segments)

    def _slugify(self, value: str) -> str:
        """Convert a human location name to a Mubawab-like URL slug."""
        ascii_value = self._ascii_fold(value)
        ascii_value = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_value)
        ascii_value = re.sub(r'-+', '-', ascii_value)
        return ascii_value.strip('-').lower()

    def _normalized(self, value: str) -> str:
        """Normalize strings for accent-insensitive matching."""
        ascii_value = self._ascii_fold(value)
        ascii_value = re.sub(r'[^\w\s/:+>-]', '', ascii_value.lower())
        ascii_value = re.sub(r'\s+', ' ', ascii_value)
        return ascii_value.strip()

    def _ascii_fold(self, value: str) -> str:
        """Remove accents and non-breaking spaces."""
        normalized = unicodedata.normalize('NFKD', str(value or '').replace('\xa0', ' '))
        return normalized.encode('ascii', 'ignore').decode('ascii')
