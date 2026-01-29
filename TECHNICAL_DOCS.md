# Technical Documentation - Tayara.tn Scraper

## Architecture Overview

### Design Principles

1. **Modularity**: Each component (scraping, export, database) is independent
2. **Configurability**: Centralized configuration for easy customization
3. **Resilience**: Multiple fallback strategies for data extraction
4. **Scalability**: Ready for pipeline integration and parallel processing
5. **Maintainability**: Clean code with extensive documentation

### Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Main Entry Point                     │
│                       (main.py)                          │
└────────────────────┬───────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    ┌────▼───┐  ┌────▼────┐  ┌──▼──────┐
    │Scraper │  │Exporter │  │Database │
    │Module  │  │Module   │  │Module   │
    └────┬───┘  └────┬────┘  └──┬──────┘
         │           │           │
    ┌────▼───────────▼───────────▼──────┐
    │        Configuration Module         │
    │           (config.py)               │
    └────────────────────────────────────┘
```

## Module Deep Dive

### 1. Scraper Module (`scraper.py`)

**Purpose**: Core web scraping logic

**Key Classes**:
- `TayaraScraper`: Main scraper class

**Key Methods**:

#### `_make_request(url, retry_count=0)`
Handles HTTP requests with retry logic.

```python
def _make_request(self, url: str, retry_count: int = 0) -> Optional[requests.Response]:
    """
    Makes request with:
    - Random delay (rate limiting)
    - Exponential backoff on failures
    - Request timeout
    - Error logging
    """
```

**Retry Strategy**:
- Initial delay: 2-4 seconds (random)
- Backoff factor: 2
- Max retries: 3
- Total possible delay: Up to ~16 seconds

#### `get_listing_links(page)`
Extracts listing URLs from search results page.

**Strategy**:
1. **Primary**: Look for links containing `/ad/` or `/ads/`
2. **Fallback**: Search for common CSS classes (`ad-card`, `listing-card`)
3. **Validation**: Filter out non-listing pages

**Pagination Detection**:
- Looks for "Next" button or page links
- Checks listing count vs expected
- Returns `(listing_urls, has_next_page)`

#### `parse_listing(url)`
Parses individual listing page.

**Extraction Flow**:
```
URL → HTML → BeautifulSoup → Extract Fields → Validate → Return Dict
```

**Field Extraction Strategies**:

1. **Title**:
   - `<h1>` tag
   - `og:title` meta property
   - `<title>` tag with cleanup

2. **Price**:
   - Class/data attributes with "price"
   - Regex pattern: `(\d+)\s*(TND|DT|€)`
   - Currency symbol detection

3. **Location**:
   - Class/data attributes with "location"
   - Breadcrumb parsing
   - Structured parsing: "City, Governorate, Neighborhood"

4. **Criteria**:
   - Definition lists (`<dl>`)
   - Tables with key-value pairs
   - Divs with label/value pattern

5. **Images**:
   - Gallery/carousel containers
   - Lazy-loaded images (`data-src`)
   - Quality filtering (skip icons <100px)

### 2. Data Exporter Module (`data_exporter.py`)

**Purpose**: Data processing and export

**Key Classes**:
- `DataExporter`: Handles CSV/JSON export

**Key Functions**:

#### `export_to_csv(listings)`
Exports to CSV with proper encoding.

**Features**:
- UTF-8-BOM encoding (Excel-compatible)
- Field ordering (important fields first)
- Nested structure flattening
- JSON serialization for complex fields

**Field Ordering Logic**:
```python
priority_fields = [
    'listing_id', 'title', 'price_numeric', # Essential
    'category', 'location', ...             # Important
]
remaining = sorted(all_fields - priority)   # Alphabetical
```

#### `normalize_listings(listings)`
Post-processing normalization.

**Operations**:
- Deduplication by listing_id
- Type conversions (prices to float)
- Boolean field standardization
- List validation for image_urls

#### `validate_data_quality(listings)`
Comprehensive quality validation.

**Checks**:
1. Required field presence
2. Price validity (> 0)
3. Image availability
4. Location completeness

**Quality Score Formula**:
```python
penalties = (
    missing_fields * 2 +
    invalid_prices * 1 +
    missing_images * 0.5 +
    incomplete_location * 1
)
score = max(0, 100 - (penalties / max_possible * 100))
```

### 3. Database Module (`database.py`)

**Purpose**: Database integration via SQLAlchemy

**Key Classes**:
- `Listing`: SQLAlchemy ORM model
- `DatabaseManager`: Database operations

**Schema Design**:

```sql
CREATE TABLE listings (
    id SERIAL PRIMARY KEY,
    listing_id VARCHAR(100) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    price_numeric NUMERIC(15,2),
    currency VARCHAR(10),
    category VARCHAR(50),
    city VARCHAR(100),
    governorate VARCHAR(100),
    criteria JSON,                -- Flexible criteria storage
    image_urls JSON,              -- Array of image URLs
    scraped_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_listing_id ON listings(listing_id);
CREATE INDEX idx_city ON listings(city);
CREATE INDEX idx_category ON listings(category);
CREATE INDEX idx_scraped_at ON listings(scraped_at);
```

**Upsert Logic**:

PostgreSQL (native support):
```python
stmt = insert(Listing).values(**data)
stmt = stmt.on_conflict_do_update(
    index_elements=['listing_id'],
    set_={...}  # Fields to update
)
```

Other databases (fallback):
```python
existing = session.query(Listing).filter_by(
    listing_id=data['listing_id']
).first()

if existing:
    # Update
    for key, value in data.items():
        setattr(existing, key, value)
else:
    # Insert
    listing = Listing(**data)
    session.add(listing)
```

### 4. Configuration Module (`config.py`)

**Purpose**: Centralized configuration

**Configuration Sections**:

1. **Base URLs and Endpoints**
2. **Request Parameters** (delays, timeouts, retries)
3. **Output Settings** (directories, file naming)
4. **Data Extraction** (currency mappings, date formats)
5. **Logging Configuration**
6. **Advanced Features** (Playwright, database, images)
7. **Debug Options**

**Environment-Specific Configs**:
```python
# Development
DEBUG_MODE = True
SAMPLE_SIZE = 10
SAVE_HTML_SNAPSHOTS = True

# Production
DEBUG_MODE = False
SAMPLE_SIZE = None
SAVE_HTML_SNAPSHOTS = False
```

## Selector Strategy Details

### Why Multiple Strategies?

Websites change their HTML structure frequently. Multiple extraction strategies ensure the scraper continues working even after layout changes.

### Selector Priority System

```python
# Example: Price extraction
strategies = [
    # 1. Specific class/attribute (most reliable when working)
    soup.find('span', class_='price-amount'),
    
    # 2. Semantic attributes
    soup.find('span', itemprop='price'),
    
    # 3. Pattern matching
    soup.find('span', class_=re.compile(r'price|prix', re.I)),
    
    # 4. Fallback to text search
    re.search(r'(\d+)\s*TND', soup.get_text()),
]
```

### Selector Maintenance

When selectors break:

1. **Enable HTML snapshots**: `SAVE_HTML_SNAPSHOTS = True`
2. **Run with debug**: `python main.py --debug --sample-size 1`
3. **Examine saved HTML**: Check `data/raw/page_1.html`
4. **Update selectors**: Modify extraction methods in `scraper.py`
5. **Test thoroughly**: Run with `--sample-size 10`

## Error Handling Strategy

### Levels of Error Handling

1. **Request Level**: HTTP errors, timeouts
   - Retry with exponential backoff
   - Log error and continue to next URL

2. **Parse Level**: Missing fields, invalid data
   - Use fallback selectors
   - Return None for failed parses
   - Continue to next listing

3. **Export Level**: File I/O errors
   - Log error
   - Raise exception (critical failures)

4. **Database Level**: Connection errors, constraint violations
   - Rollback transaction
   - Log error with context
   - Raise exception

### Logging Strategy

**Log Levels**:
- **DEBUG**: Detailed execution flow, selector attempts
- **INFO**: Progress updates, successful operations
- **WARNING**: Missing data, fallback usage
- **ERROR**: Failed requests, parsing errors
- **CRITICAL**: System failures, database errors

**Log Locations**:
- **Console**: INFO and above (user feedback)
- **File**: DEBUG and above (troubleshooting)

## Performance Considerations

### Request Rate Limiting

```python
# Random delay prevents patterns
delay = random.uniform(2.0, 4.0)  # 2-4 seconds
time.sleep(delay)

# Respects server resources
# Average: ~3 seconds per request
# ~20 listings per minute
# ~1200 listings per hour
```

### Memory Management

**Streaming vs Batch Processing**:

Current implementation uses batch processing:
```python
listings = []  # Accumulate in memory
for page in pages:
    for listing_url in get_listing_links(page):
        data = parse_listing(listing_url)
        listings.append(data)

# Export all at once
export_to_csv(listings)
```

For very large scrapes (10,000+ listings):
```python
# Stream to file
with open('listings.csv', 'w') as f:
    writer = csv.DictWriter(f, fieldnames=...)
    writer.writeheader()
    
    for page in pages:
        for listing_url in get_listing_links(page):
            data = parse_listing(listing_url)
            writer.writerow(data)  # Write immediately
```

### Parallelization Options

**Option 1: Threading** (I/O-bound tasks)
```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(parse_listing, url) 
               for url in listing_urls]
    listings = [f.result() for f in futures]
```

**Option 2: Multiprocessing** (CPU-bound tasks)
```python
from multiprocessing import Pool

with Pool(processes=4) as pool:
    listings = pool.map(parse_listing, listing_urls)
```

**Caution**: Implement rate limiting at pool level to avoid overwhelming servers.

## Data Quality Framework

### Validation Rules

1. **Required Fields**: Must be present and non-empty
2. **Data Types**: Must match expected types (numeric, date, etc.)
3. **Value Ranges**: Prices must be positive, dates valid
4. **Referential Integrity**: URLs must be valid, IDs unique

### Quality Metrics

**Completeness**:
```
completeness = (non_null_fields / total_fields) * 100
```

**Accuracy**: Manual verification of sample
**Consistency**: Cross-field validation (e.g., price vs category)
**Timeliness**: Scrape frequency and date freshness

## Testing Strategy

### Unit Tests

```python
# test_scraper.py
def test_extract_price():
    html = '<span class="price">25,000 TND</span>'
    soup = BeautifulSoup(html, 'html.parser')
    result = scraper._extract_price(soup)
    assert result['price_numeric'] == 25000
    assert result['currency'] == 'TND'
```

### Integration Tests

```python
def test_full_scrape_pipeline():
    # Scrape sample
    config.SAMPLE_SIZE = 5
    scraper = TayaraScraper()
    listings = scraper.scrape_all()
    
    # Validate
    assert len(listings) > 0
    assert all('title' in l for l in listings)
    
    # Export
    exporter = DataExporter()
    csv_path = exporter.export_to_csv(listings)
    assert csv_path.exists()
```

### Manual Testing Checklist

- [ ] Scrape completes without errors
- [ ] All expected fields present
- [ ] Data makes logical sense (prices reasonable, locations valid)
- [ ] CSV opens properly in Excel
- [ ] JSON is valid and readable
- [ ] Database insertion successful
- [ ] Logs contain expected information

## Deployment Considerations

### Production Environment Setup

1. **Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration**:
   - Set `DEBUG_MODE = False`
   - Configure database credentials
   - Set appropriate `MAX_PAGES`
   - Adjust rate limiting if needed

3. **Monitoring**:
   - Set up log rotation
   - Monitor disk space (logs and data)
   - Set up alerts for failures
   - Track success rate and duration

4. **Scheduling**:
   - Cron or Airflow for regular execution
   - Off-peak hours to reduce server load
   - Reasonable frequency (daily or weekly)

### Security Best Practices

1. **Credentials**: Use environment variables or secrets manager
   ```python
   import os
   DB_PASSWORD = os.getenv('TAYARA_DB_PASSWORD')
   ```

2. **User-Agent**: Identify yourself honestly
   ```python
   USER_AGENT = 'TayaraBot/1.0 (+http://yoursite.com/bot)'
   ```

3. **Rate Limiting**: Respect website resources

4. **Error Handling**: Don't expose system internals in logs

## Troubleshooting Guide

### Common Issues

**Issue**: No listings found
- **Check**: Website structure changed
- **Solution**: Update selectors, enable HTML snapshots

**Issue**: Timeout errors
- **Check**: Network connectivity, server load
- **Solution**: Increase `REQUEST_TIMEOUT`, reduce request rate

**Issue**: Missing fields
- **Check**: Website removed fields or changed structure
- **Solution**: Update extraction logic, add fallbacks

**Issue**: Database errors
- **Check**: Connection string, credentials, schema
- **Solution**: Verify database setup, check logs

### Debug Workflow

1. Enable debug mode: `--debug`
2. Limit sample size: `--sample-size 1`
3. Save HTML: `SAVE_HTML_SNAPSHOTS = True`
4. Examine logs: Check `data/logs/`
5. Inspect HTML: Review saved snapshots
6. Test selectors: Use BeautifulSoup in Python REPL
7. Update code: Modify extraction methods
8. Test again: Verify fixes work

## Future Enhancements

### Planned Features

1. **JavaScript Rendering**: Full Playwright integration
2. **Image Download**: Store images locally or in cloud storage
3. **Change Detection**: Track price changes over time
4. **Real-time Alerts**: Notify on new listings matching criteria
5. **API Endpoint**: REST API for accessing scraped data
6. **Dashboard**: Web UI for viewing and filtering listings
7. **Machine Learning**: Price prediction, fraud detection

### Extension Points

**Custom Extractors**:
```python
class CustomTayaraScraper(TayaraScraper):
    def _extract_custom_field(self, soup):
        # Custom extraction logic
        pass
```

**Custom Exporters**:
```python
class XMLExporter(DataExporter):
    def export_to_xml(self, listings):
        # XML export logic
        pass
```

**Custom Validators**:
```python
def custom_validation(listing):
    # Custom validation rules
    return is_valid
```

## Contributing Guidelines

1. **Code Style**: Follow PEP 8
2. **Documentation**: Update docstrings and README
3. **Testing**: Add tests for new features
4. **Logging**: Use appropriate log levels
5. **Error Handling**: Handle exceptions gracefully
6. **Configuration**: Add new settings to config.py

## License and Legal

**Important**: Web scraping legality varies by jurisdiction and website terms of service.

**Responsibilities**:
- Review tayara.tn Terms of Service
- Respect robots.txt directives
- Use reasonable rate limits
- Don't misuse scraped data
- Consider data privacy laws (GDPR, etc.)

**This scraper is provided for educational purposes.**

---

## Additional Resources

- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Requests Documentation](https://docs.python-requests.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Web Scraping Best Practices](https://www.scrapehero.com/web-scraping-best-practices/)

## Support

For issues, questions, or contributions:
1. Check documentation (README.md and this file)
2. Review logs and enable debug mode
3. Search for similar issues
4. Create detailed issue report with:
   - Python version
   - Error messages
   - Steps to reproduce
   - Log snippets

---

**Last Updated**: January 2024  
**Version**: 1.0.0
