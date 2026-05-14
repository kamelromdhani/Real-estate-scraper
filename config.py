"""
Configuration file for the Tunisian real estate scrapers.
Centralizes all settings for easy modification and deployment.
"""

import os
from pathlib import Path

# ============================================================================
# BASE CONFIGURATION
# ============================================================================

SOURCE_CONFIGS = {
    'tayara': {
        'display_name': 'Tayara.tn',
        'source_domain': 'tayara.tn',
        'base_url': 'https://www.tayara.tn',
        'immobilier_url': 'https://www.tayara.tn/listing/c/Immobilier',
        'output_dir': Path("data/tayara_scrape"),
        'filename_prefix': 'tayara',
    },
    'menzili': {
        'display_name': 'Menzili.tn',
        'source_domain': 'menzili.tn',
        'base_url': 'https://www.menzili.tn',
        'immobilier_url': 'https://www.menzili.tn/immo/immobilier-tunisie',
        'output_dir': Path("data/menzili_scrape"),
        'filename_prefix': 'menzili',
    },
    'mubawab': {
        'display_name': 'Mubawab.tn',
        'source_domain': 'mubawab.tn',
        'base_url': 'https://www.mubawab.tn',
        'immobilier_url': 'https://www.mubawab.tn/fr/sc/appartements-a-vendre',
        'output_dir': Path("data/mubawab_scrape"),
        'filename_prefix': 'mubawab',
    },
}

DEFAULT_SOURCE = "tayara"
ACTIVE_SOURCE = DEFAULT_SOURCE

BASE_URL = SOURCE_CONFIGS[ACTIVE_SOURCE]['base_url']
IMMOBILIER_URL = SOURCE_CONFIGS[ACTIVE_SOURCE]['immobilier_url']
SOURCE_DISPLAY_NAME = SOURCE_CONFIGS[ACTIVE_SOURCE]['display_name']
SOURCE_DOMAIN = SOURCE_CONFIGS[ACTIVE_SOURCE]['source_domain']
FILENAME_PREFIX = SOURCE_CONFIGS[ACTIVE_SOURCE]['filename_prefix']

# ============================================================================
# SCRAPING PARAMETERS
# ============================================================================

# Request headers to mimic a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8,fr;q=0.7',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
}

# Rate limiting and retry settings
REQUEST_DELAY_MIN = 2.0  # Minimum seconds between requests
REQUEST_DELAY_MAX = 4.0  # Maximum seconds between requests
REQUEST_TIMEOUT = 30     # Request timeout in seconds
MAX_RETRIES = 3          # Maximum retry attempts
BACKOFF_FACTOR = 2       # Exponential backoff multiplier

# Pagination settings
MAX_PAGES = None         # Set to None for unlimited, or integer to limit
LISTINGS_PER_PAGE = 80   # Approximate listings per page (for progress tracking)

# ============================================================================
# OUTPUT CONFIGURATION
# ============================================================================

# Output directory structure
OUTPUT_DIR = SOURCE_CONFIGS[ACTIVE_SOURCE]['output_dir']
RAW_DATA_DIR = OUTPUT_DIR / "raw"
PROCESSED_DATA_DIR = OUTPUT_DIR / "processed"
LOGS_DIR = OUTPUT_DIR / "logs"
IMAGES_DIR = OUTPUT_DIR / "images"  # For future image download feature

# Output file naming
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
CSV_FILENAME_TEMPLATE = "{source}_listings_{timestamp}.csv"
JSON_FILENAME_TEMPLATE = "{source}_listings_{timestamp}.json"
LOG_FILENAME_TEMPLATE = "scraper_{timestamp}.log"

# ============================================================================
# DATA EXTRACTION CONFIGURATION
# ============================================================================

# Field mappings for normalization
CURRENCY_SYMBOLS = {
    'TND': 'TND',
    'DT': 'TND',
    'dt': 'TND',
    'EUR': 'EUR',
    '€': 'EUR',
    'USD': 'USD',
    '$': 'USD',
}

# Date format patterns (for parsing)
DATE_PATTERNS = [
    "%d/%m/%Y",           # 25/01/2024
    "%Y-%m-%d",           # 2024-01-25
    "%d-%m-%Y",           # 25-01-2024
    "%B %d, %Y",          # January 25, 2024
]

# Category mappings (for normalization)
CATEGORY_MAPPINGS = {
    'appartement': 'apartment',
    'apartment': 'apartment',
    'maison': 'house',
    'house': 'house',
    'villa': 'villa',
    'terrain': 'land',
    'land': 'land',
    'bureau': 'office',
    'office': 'office',
    'local commercial': 'commercial',
    'commercial': 'commercial',
    'vente': 'sale',
    'location': 'rent',
    'rent': 'rent',
    'sale': 'sale',
}

# Expected criteria fields to extract (these may vary by listing)
EXPECTED_CRITERIA = [
    'surface',
    'surface_area',
    'rooms',
    'bedrooms',
    'bathrooms',
    'floor',
    'furnished',
    'garage',
    'garden',
    'pool',
    'elevator',
    'balcony',
    'terrace',
]

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Console logging
CONSOLE_LOG_ENABLED = True
CONSOLE_LOG_LEVEL = "INFO"

# File logging
FILE_LOG_ENABLED = True
FILE_LOG_LEVEL = "DEBUG"

# ============================================================================
# ADVANCED FEATURES
# ============================================================================

# Dynamic content detection
USE_PLAYWRIGHT = False  # Set to True if content is JavaScript-rendered
PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_TIMEOUT = 30000  # milliseconds

# Image download settings
DOWNLOAD_IMAGES = False  # Set to True to download listing images
IMAGE_QUALITY = "high"   # 'high', 'medium', 'low'
MAX_IMAGES_PER_LISTING = 10

# Database integration (for pipeline integration)
USE_DATABASE = False
DATABASE_TYPE = "postgresql"  # postgresql, mysql, sqlite
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'tayara_db',
    'user': 'scraper',
    'password': 'your_password_here',
}

# Data quality checks
ENABLE_DATA_VALIDATION = True
MIN_REQUIRED_FIELDS = ['title', 'listing_url', 'price']  # Minimum fields for valid listing
MIN_DATE_POSTED = None  # YYYY-MM-DD; keep listings posted on or after this date

# Mubawab search builder settings
MUBAWAB_TRANSACTION = "sale"  # sale or rent
MUBAWAB_PROPERTY_TYPE = "logement"  # logement, terrain, apartment, house, villa, etc.
MUBAWAB_LOCATION = None  # Slug or name, e.g. la-marsa or "La Marsa"
MUBAWAB_LOCATION_LEVEL = "st"  # st, ct, cd, sd, is, or sc
MUBAWAB_SEARCH_URL = None  # Exact Mubawab search URL override

# ============================================================================
# DEBUGGING & DEVELOPMENT
# ============================================================================

DEBUG_MODE = False        # Enable verbose debugging
SAVE_HTML_SNAPSHOTS = False  # Save HTML of pages for debugging
DRY_RUN = False          # Run without saving data (testing)
SAMPLE_SIZE = None       # Set to integer to limit scraping (for testing)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def ensure_directories():
    """Create all necessary directories if they don't exist"""
    directories = [
        OUTPUT_DIR,
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        LOGS_DIR,
        IMAGES_DIR,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def set_output_dir(output_dir):
    """Update output directory globals and create the directory tree."""
    global OUTPUT_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, LOGS_DIR, IMAGES_DIR

    OUTPUT_DIR = Path(output_dir)
    RAW_DATA_DIR = OUTPUT_DIR / "raw"
    PROCESSED_DATA_DIR = OUTPUT_DIR / "processed"
    LOGS_DIR = OUTPUT_DIR / "logs"
    IMAGES_DIR = OUTPUT_DIR / "images"
    ensure_directories()

def set_active_source(source):
    """Switch scraper-wide source settings."""
    global ACTIVE_SOURCE, BASE_URL, IMMOBILIER_URL, SOURCE_DISPLAY_NAME
    global SOURCE_DOMAIN, FILENAME_PREFIX

    if source not in SOURCE_CONFIGS:
        valid_sources = ', '.join(sorted(SOURCE_CONFIGS))
        raise ValueError(f"Unsupported source '{source}'. Expected one of: {valid_sources}")

    source_config = SOURCE_CONFIGS[source]
    ACTIVE_SOURCE = source
    BASE_URL = source_config['base_url']
    IMMOBILIER_URL = source_config['immobilier_url']
    SOURCE_DISPLAY_NAME = source_config['display_name']
    SOURCE_DOMAIN = source_config['source_domain']
    FILENAME_PREFIX = source_config['filename_prefix']
    set_output_dir(source_config['output_dir'])

def get_output_filename(template, timestamp, source=None):
    """Generate output filename with timestamp"""
    return template.format(
        timestamp=timestamp,
        source=source or FILENAME_PREFIX,
    )

# Auto-create directories on import
ensure_directories()
