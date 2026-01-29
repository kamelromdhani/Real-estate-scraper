# Installation & Setup Guide - Tayara.tn Scraper

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment tool (recommended)
- Internet connection
- 100 MB free disk space (minimum)

### System Requirements
- **RAM**: 512 MB minimum, 2 GB recommended
- **CPU**: Any modern processor
- **OS**: Linux, macOS, or Windows

## 🚀 Quick Installation (5 minutes)

### Step 1: Download Files

Download all project files to a directory:
```bash
mkdir tayara-scraper
cd tayara-scraper
# Copy all .py, .md, .txt files here
```

### Step 2: Create Virtual Environment (Recommended)

**Linux/macOS**:
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows**:
```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- requests (HTTP library)
- beautifulsoup4 (HTML parsing)
- lxml (XML/HTML parser)

### Step 4: Verify Installation

```bash
python main.py --help
```

You should see the help message with available options.

### Step 5: Test Run

```bash
python example.py
```

This runs a test scrape with 5 sample listings.

## 🔧 Detailed Installation

### Option 1: Basic Installation (No Database)

Perfect for CSV/JSON export only:

```bash
# Install core dependencies
pip install requests beautifulsoup4 lxml

# Test
python main.py --sample-size 5 --export-format csv
```

### Option 2: With Database Support

For PostgreSQL integration:

```bash
# Install core + database
pip install -r requirements.txt
pip install psycopg2-binary sqlalchemy

# Configure database in config.py
# Set USE_DATABASE = True
# Update DATABASE_CONFIG with your credentials

# Test database connection
python -c "from database import DatabaseManager; db = DatabaseManager(); db.create_tables(); print('Database OK')"
```

### Option 3: With Playwright (JavaScript Support)

For websites with heavy JavaScript:

```bash
# Install playwright
pip install playwright

# Install browser
playwright install chromium

# Test with Playwright
python main.py --use-playwright --sample-size 5
```

### Option 4: Full Installation (All Features)

```bash
# Install everything
pip install -r requirements.txt
pip install playwright pandas
playwright install chromium

# Verify
python -c "import requests, bs4, playwright, pandas, sqlalchemy; print('All packages OK')"
```

## 📁 Project Structure Setup

After installation, your directory should look like:

```
tayara-scraper/
├── config.py              # Configuration
├── scraper.py            # Core scraper
├── data_exporter.py      # Export utilities
├── database.py           # Database integration
├── logger_config.py      # Logging setup
├── main.py               # Main entry point
├── example.py            # Examples
├── requirements.txt      # Dependencies
├── README.md            # User guide
├── TECHNICAL_DOCS.md    # Developer docs
├── PROJECT_SUMMARY.md   # Project overview
├── airflow_dag_example.py # Airflow integration
├── .gitignore           # Git ignore
└── data/                # Auto-created on first run
    └── tayara_scrape/
        ├── raw/         # HTML snapshots (if enabled)
        ├── processed/   # CSV/JSON output
        ├── logs/        # Execution logs
        └── images/      # Downloaded images (if enabled)
```

## ⚙️ Configuration

### Basic Configuration

Edit `config.py` to customize:

```python
# Rate limiting (adjust for your needs)
REQUEST_DELAY_MIN = 2.0  # Seconds between requests
REQUEST_DELAY_MAX = 4.0

# Pagination
MAX_PAGES = None  # None = unlimited, or set integer

# Output
OUTPUT_DIR = Path("data/tayara_scrape")
```

### Database Configuration

For database integration:

```python
USE_DATABASE = True
DATABASE_TYPE = "postgresql"  # or "mysql", "sqlite"
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'tayara_db',
    'user': 'your_username',
    'password': 'your_password',
}
```

### Advanced Configuration

```python
# Debug mode
DEBUG_MODE = True  # Enable for troubleshooting

# Save HTML for debugging
SAVE_HTML_SNAPSHOTS = True

# Sample size (for testing)
SAMPLE_SIZE = 10  # Limit number of listings
```

## 🗄️ Database Setup

### PostgreSQL Setup

```bash
# 1. Install PostgreSQL
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql

# 2. Create database and user
sudo -u postgres psql

# In psql:
CREATE DATABASE tayara_db;
CREATE USER tayara_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE tayara_db TO tayara_user;
\q

# 3. Update config.py with credentials

# 4. Create tables
python -c "from database import DatabaseManager; db = DatabaseManager(); db.create_tables()"
```

### SQLite Setup (Simpler)

```python
# In config.py
USE_DATABASE = True
DATABASE_TYPE = "sqlite"
DATABASE_CONFIG = {
    'database': 'tayara_listings'  # Creates tayara_listings.db
}

# Tables created automatically on first run
```

## 🌐 Network Configuration

### Proxy Setup (if needed)

Edit `config.py`:

```python
PROXIES = {
    'http': 'http://proxy.example.com:8080',
    'https': 'https://proxy.example.com:8080',
}

# Then in scraper.py, add to requests:
self.session.proxies.update(config.PROXIES)
```

### Firewall Rules

Ensure outbound HTTPS (port 443) is allowed to tayara.tn

## 🐛 Troubleshooting Installation

### Issue: "No module named 'requests'"
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

### Issue: "Permission denied" on Linux
```bash
# Solution: Use virtual environment or add --user
pip install --user -r requirements.txt
```

### Issue: "playwright: command not found"
```bash
# Solution: Install playwright browsers
python -m playwright install
```

### Issue: Database connection failed
```bash
# Check PostgreSQL is running
sudo service postgresql status

# Test connection
psql -h localhost -U tayara_user -d tayara_db
```

### Issue: "ModuleNotFoundError: No module named 'config'"
```bash
# Make sure you're in the project directory
cd /path/to/tayara-scraper
python main.py
```

## 🧪 Verify Installation

Run this verification script:

```python
# verify_install.py
import sys

def check_module(name):
    try:
        __import__(name)
        print(f"✓ {name}")
        return True
    except ImportError:
        print(f"✗ {name} - MISSING")
        return False

print("Checking installation...")
modules = ['requests', 'bs4', 'lxml', 'config', 'scraper']
all_ok = all(check_module(m) for m in modules)

if all_ok:
    print("\n✓ All required modules installed!")
    print("\nRun: python example.py")
else:
    print("\n✗ Some modules missing. Run: pip install -r requirements.txt")
```

## 🎯 First Run

### Test with Examples

```bash
# Run all examples (recommended first step)
python example.py

# Or run specific example
python example.py 1  # Basic scraping
python example.py 2  # Data export
python example.py 3  # Quality check
```

### Production Run

```bash
# Scrape first 5 pages
python main.py --max-pages 5

# Check output
ls -l data/tayara_scrape/processed/

# View CSV
head data/tayara_scrape/processed/tayara_listings_*.csv
```

## 📊 Performance Tuning

### Faster Scraping (Use with Caution)

```python
# config.py
REQUEST_DELAY_MIN = 1.0  # Reduced from 2.0
REQUEST_DELAY_MAX = 2.0  # Reduced from 4.0
```

⚠️ **Warning**: Too fast = risk of IP ban

### Memory Optimization

For large scrapes (10,000+ listings):

```python
# In scraper.py, implement streaming:
# Write to CSV immediately instead of accumulating in memory
```

## 🔄 Updating

### Update Python Packages

```bash
pip install --upgrade -r requirements.txt
```

### Update Scraper Code

When website structure changes:

1. Enable HTML snapshots: `SAVE_HTML_SNAPSHOTS = True`
2. Run small test: `python main.py --sample-size 1`
3. Examine saved HTML in `data/raw/`
4. Update selectors in `scraper.py`
5. Test thoroughly: `python example.py`

## 🐳 Docker Installation (Optional)

### Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory
RUN mkdir -p data/tayara_scrape

CMD ["python", "main.py", "--max-pages", "10"]
```

### Build and Run

```bash
# Build
docker build -t tayara-scraper .

# Run
docker run -v $(pwd)/data:/app/data tayara-scraper

# With custom args
docker run -v $(pwd)/data:/app/data tayara-scraper python main.py --sample-size 20
```

## 📅 Scheduling (Optional)

### Cron Job (Linux/macOS)

```bash
# Edit crontab
crontab -e

# Add line for daily run at 2 AM
0 2 * * * cd /path/to/tayara-scraper && /path/to/venv/bin/python main.py --max-pages 20
```

### Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 2:00 AM
4. Action: Start a Program
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `main.py --max-pages 20`
   - Start in: `C:\path\to\tayara-scraper`

### Airflow (Advanced)

See `airflow_dag_example.py` for complete setup.

## 🔒 Security Considerations

### Credentials Management

Never commit credentials to Git:

```bash
# Create .env file (add to .gitignore)
echo "DB_PASSWORD=your_password" > .env

# Load in config.py
import os
from dotenv import load_dotenv
load_dotenv()
DB_PASSWORD = os.getenv('DB_PASSWORD')
```

### Network Security

- Use HTTPS only
- Consider VPN for sensitive scraping
- Rotate User-Agents if needed
- Respect robots.txt

## 📞 Getting Help

If you encounter issues:

1. Check this installation guide
2. Review README.md
3. Enable debug mode: `python main.py --debug`
4. Check logs: `cat data/tayara_scrape/logs/*.log`
5. Run examples: `python example.py`

## ✅ Installation Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Config.py reviewed and customized
- [ ] Test run successful (`python example.py`)
- [ ] Output directory created (`data/tayara_scrape/`)
- [ ] Database configured (if using)
- [ ] First scrape completed (`python main.py --sample-size 10`)
- [ ] Output files verified (CSV/JSON in `processed/`)
- [ ] Logs reviewed (in `logs/`)

## 🎉 You're Ready!

Installation complete! Next steps:

1. Read README.md for usage guide
2. Run `python example.py` to learn the scraper
3. Customize `config.py` for your needs
4. Run production scrape: `python main.py`
5. Review TECHNICAL_DOCS.md for advanced features

---

**Happy Scraping!** 🚀
