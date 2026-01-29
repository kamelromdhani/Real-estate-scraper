# Tayara.tn Real Estate Scraper

A robust, production-ready web scraper for extracting real estate listings from tayara.tn (Immobilier section). Built with Python, featuring comprehensive data extraction, quality validation, and pipeline integration capabilities.

## 🎯 Features

### Core Functionality
- **Comprehensive Data Extraction**: Extracts 15+ fields per listing including title, price, location, features, images, and more
- **Multi-format Export**: Outputs to both CSV and JSON with proper UTF-8 encoding for Arabic/French text
- **Intelligent Pagination**: Automatic detection and traversal of multiple pages
- **Robust Error Handling**: Retry logic with exponential backoff, detailed logging
- **Rate Limiting**: Polite scraping with configurable delays between requests
- **Data Validation**: Built-in quality checks and validation scoring

### Advanced Features
- **Dynamic Criteria Extraction**: Automatically extracts all listing features (surface, rooms, etc.)
- **Smart ID Generation**: Extracts IDs from URLs or generates stable hashes
- **Image URL Collection**: Captures all listing images with quality options
- **Flexible Configuration**: Centralized config file for easy customization
- **Pipeline Ready**: Airflow DAG included for production deployments
- **Modular Architecture**: Clean separation of concerns for maintainability

## 📋 Requirements

- Python 3.8+
- See `requirements.txt` for full dependency list

### Core Dependencies
```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.1.0
```

### Optional Dependencies
```
playwright>=1.40.0  # For JavaScript-rendered content
pandas>=2.1.0       # For advanced analysis
psycopg2-binary     # For PostgreSQL integration
```

## 🚀 Installation

### Basic Setup
```bash
# Clone or download the project
cd tayara-scraper

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### With Playwright (for dynamic content)
```bash
pip install playwright
playwright install chromium
```

## 💻 Usage

### Basic Usage

```bash
# Run full scrape (all pages)
python main.py

# Scrape first 5 pages
python main.py --max-pages 5

# Test with 10 listings
python main.py --sample-size 10

# Enable debug logging
python main.py --debug

# Dry run (no data saved)
python main.py --dry-run
```

### Advanced Usage

```bash
# Use Playwright for JavaScript content
python main.py --use-playwright

# Export only to CSV
python main.py --export-format csv

# Custom output directory
python main.py --output-dir /path/to/output
```

### Programmatic Usage

```python
from scraper import TayaraScraper
from data_exporter import DataExporter, normalize_listings

# Initialize scraper
scraper = TayaraScraper()

# Scrape listings
listings = scraper.scrape_all(max_pages=5)

# Normalize data
normalized = normalize_listings(listings)

# Export to CSV and JSON
exporter = DataExporter()
exporter.export_to_csv(normalized)
exporter.export_to_json(normalized)

# Generate summary report
report = exporter.generate_summary_report(normalized)
print(f"Quality score: {report['quality_score']}")
```

## 📁 Project Structure

```
tayara-scraper/
├── config.py              # Centralized configuration
├── scraper.py            # Core scraping logic
├── data_exporter.py      # Data processing and export
├── logger_config.py      # Logging setup
├── main.py               # Main entry point
├── airflow_dag_example.py # Airflow integration example
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── data/                # Output directory (auto-created)
    ├── raw/            # Raw HTML snapshots (if enabled)
    ├── processed/      # Final CSV/JSON files
    ├── logs/           # Execution logs
    └── images/         # Downloaded images (if enabled)
```

## 🔧 Configuration

Edit `config.py` to customize scraper behavior:

### Key Configuration Options

```python
# Scraping parameters
REQUEST_DELAY_MIN = 2.0      # Seconds between requests
REQUEST_DELAY_MAX = 4.0
MAX_RETRIES = 3
MAX_PAGES = None             # None = unlimited

# Output settings
OUTPUT_DIR = Path("data/tayara_scrape")
DOWNLOAD_IMAGES = False      # Set True to download images

# Data validation
ENABLE_DATA_VALIDATION = True
MIN_REQUIRED_FIELDS = ['title', 'listing_url', 'price']

# Debug options
DEBUG_MODE = False
SAVE_HTML_SNAPSHOTS = False  # Save pages for debugging
```

## 📊 Output Format

### CSV Output
```csv
listing_id,title,price_numeric,currency,category,city,governorate,...
hash_abc123,"Appartement S+2 à Tunis",250000,TND,apartment,Tunis,Tunis,...
```

### JSON Output
```json
{
  "metadata": {
    "export_timestamp": "2024-01-28T10:30:00",
    "total_listings": 150,
    "source": "tayara.tn"
  },
  "listings": [
    {
      "listing_id": "123456",
      "title": "Appartement S+2 à Tunis",
      "price_numeric": 250000,
      "currency": "TND",
      "category": "apartment",
      "location_raw": "Tunis, Ariana, Ennasr",
      "city": "Ariana",
      "governorate": "Tunis",
      "description": "Bel appartement...",
      "criteria": {
        "surface": 120,
        "rooms": 3,
        "bedrooms": 2,
        "bathrooms": 1,
        "furnished": false
      },
      "image_urls": ["url1", "url2"],
      "date_posted": "2024-01-25",
      "listing_url": "https://www.tayara.tn/ad/123456"
    }
  ]
}
```

## 🔍 Data Extraction Strategy

### Field Extraction Methods

1. **Title**: Extracted from `<h1>` tags or meta properties
2. **Price**: Regex patterns for currency + numeric extraction
3. **Category**: Breadcrumbs, URL analysis, data attributes
4. **Location**: Location elements, breadcrumbs, structured parsing
5. **Description**: Main content area with paragraph preservation
6. **Criteria**: Dynamic extraction from tables, definition lists, key-value divs
7. **Images**: Gallery/carousel detection, lazy-load handling
8. **Date**: Time elements, datetime attributes, relative date parsing

### Selector Strategy

The scraper uses a **cascading strategy** for resilience:

1. **Primary**: Specific class/attribute selectors
2. **Fallback**: Common patterns and regex
3. **URL-based**: Extract from URL structure
4. **Hash generation**: Stable IDs when no unique identifier found

This approach ensures the scraper continues working even if the website structure changes.

## 🔄 Pipeline Integration

### Airflow Integration

The included `airflow_dag_example.py` provides a complete production pipeline:

```python
# Daily scheduled scraping at 2 AM
schedule_interval='0 2 * * *'

# Pipeline tasks:
1. Create database tables
2. Scrape listings
3. Validate data quality
4. Load to PostgreSQL
5. Export CSV backup
6. Send notification
```

#### Setup Steps:

1. Copy `airflow_dag_example.py` to your Airflow DAGs folder
2. Configure database connection in Airflow UI
3. Adjust paths and settings in the DAG file
4. Enable the DAG in Airflow UI

### Database Schema Example

```sql
CREATE TABLE listings (
    id SERIAL PRIMARY KEY,
    listing_id VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    price_numeric NUMERIC,
    currency VARCHAR(10),
    category VARCHAR(50),
    city VARCHAR(100),
    governorate VARCHAR(100),
    description TEXT,
    date_posted DATE,
    listing_url TEXT NOT NULL,
    scraped_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_listing_id ON listings(listing_id);
CREATE INDEX idx_city ON listings(city);
CREATE INDEX idx_scraped_at ON listings(scraped_at);
```

### Cron Integration

For simpler scheduling:

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/scraper && /path/to/venv/bin/python main.py --max-pages 20 >> logs/cron.log 2>&1
```

## 📈 Data Quality

The scraper includes comprehensive quality validation:

### Quality Metrics
- Field completeness percentage
- Price validity checks
- Image availability
- Location data completeness
- Overall quality score (0-100)

### Quality Report Example
```json
{
  "total_listings": 150,
  "quality_score": 87.5,
  "field_completeness": {
    "title": {"count": 150, "percentage": 100},
    "price_numeric": {"count": 142, "percentage": 94.67}
  },
  "issues": {
    "missing_required_fields": [],
    "invalid_prices": 3,
    "missing_images": 12
  }
}
```

## 🛡️ Best Practices

### Ethical Scraping
- **Respect robots.txt**: Check site's robots.txt before scraping
- **Rate limiting**: Built-in delays prevent server overload
- **User-Agent**: Identifies the scraper honestly
- **No aggressive scraping**: Reasonable request frequency

### Error Handling
- Retry logic with exponential backoff
- Comprehensive logging at multiple levels
- Graceful degradation (continues on individual failures)
- Detailed error reporting

### Maintenance
- Modular design for easy updates
- Centralized configuration
- Extensive inline documentation
- Version control friendly

## 🐛 Troubleshooting

### Common Issues

**Issue**: "No listings found on page 1"
```bash
# Enable debug mode to see HTML structure
python main.py --debug --max-pages 1

# Check saved HTML snapshots
config.SAVE_HTML_SNAPSHOTS = True
```

**Issue**: "Request timeout"
```bash
# Increase timeout in config.py
REQUEST_TIMEOUT = 60  # seconds
```

**Issue**: "JavaScript-rendered content"
```bash
# Use Playwright
python main.py --use-playwright
```

### Debugging Tips

1. **Enable HTML snapshots**: Set `SAVE_HTML_SNAPSHOTS = True` in config
2. **Check logs**: Review logs in `data/tayara_scrape/logs/`
3. **Test with sample**: Use `--sample-size 5` for quick testing
4. **Verify selectors**: Inspect saved HTML to update selectors if needed

## 🔄 Updating Selectors

If the website structure changes:

1. Enable HTML snapshots in config
2. Run scraper with `--debug` flag
3. Examine saved HTML in `data/raw/`
4. Update selectors in `scraper.py`
5. Focus on these methods:
   - `_extract_title()`
   - `_extract_price()`
   - `_extract_location()`
   - `_extract_criteria()`

## 📝 Logging

Three logging levels:
- **Console**: INFO level (progress updates)
- **File**: DEBUG level (detailed execution)
- **Custom**: Configurable in `config.py`

Logs include:
- Request URLs and responses
- Parsing successes/failures
- Data validation results
- Error stack traces
- Performance metrics

## 🧪 Testing

```bash
# Quick test with 5 listings
python main.py --sample-size 5 --debug

# Dry run (no data saved)
python main.py --dry-run --max-pages 2

# Test specific features
python -c "from scraper import TayaraScraper; s = TayaraScraper(); print(s.get_listing_links(1))"
```

## 📄 License

This scraper is provided as-is for educational and research purposes. Users are responsible for:
- Complying with tayara.tn's Terms of Service
- Respecting rate limits and robots.txt
- Using scraped data ethically and legally

## 🤝 Contributing

Improvements welcome! Key areas:
- Additional field extraction
- Performance optimizations
- New export formats
- Enhanced error handling
- More pipeline integrations

## 📧 Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs in `data/tayara_scrape/logs/`
3. Enable debug mode for detailed output
4. Check if website structure has changed

## 🔮 Future Enhancements

Potential additions:
- [ ] Image download and storage
- [ ] Multi-threading for faster scraping
- [ ] MongoDB integration
- [ ] Real-time change detection
- [ ] Price history tracking
- [ ] Email alerts for new listings
- [ ] Dashboard for visualization
- [ ] API endpoint for listing data

---

**Version**: 1.0.0  
**Last Updated**: January 2024  
**Author**: Data Engineering Team
