#!/usr/bin/env python3
"""
Tunisian Real Estate Scraper - Main Entry Point

Usage:
    python main.py [options]

Options:
    --source NAME       Source to scrape: tayara, menzili, or mubawab
    --max-pages N       Limit scraping to N pages
    --sample-size N     Limit scraping to N listings (for testing)
    --min-date-posted D Keep listings posted on or after YYYY-MM-DD
    --transaction NAME  Mubawab transaction: sale or rent
    --property-type NAME Mubawab property type: logement or terrain
    --location NAME     Mubawab location name/slug
    --search-url URL    Exact Mubawab search URL override
    --output-dir PATH   Custom output directory
    --debug             Enable debug mode
    --dry-run           Run without saving data
    --use-playwright    Use Playwright for JavaScript-rendered content

Examples:
    # Scrape Menzili listings
    python main.py --source menzili --max-pages 2

    # Scrape Mubawab apartment sale listings in La Marsa
    python main.py --source mubawab --transaction sale --property-type logement --location "La Marsa"

    # Scrape Mubawab land sale listings in Tunis
    python main.py --source mubawab --transaction sale --property-type terrain --location Tunis --location-level ct

    # Scrape Menzili listings posted on or after 2025-12-01
    python main.py --source menzili --min-date-posted 2025-12-01

    # Scrape first 5 pages
    python main.py --max-pages 5
    
    # Test with 10 listings
    python main.py --sample-size 10
    
    # Full scrape with debug logging
    python main.py --debug
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path
import time
from datetime import datetime
from urllib.parse import urljoin

# Import project modules
import config
from scraper import TayaraScraper
from menzili_scraper import MenziliScraper
from mubawab_scraper import MubawabScraper
from data_exporter import (
    DataExporter,
    filter_listings_by_min_date_posted,
    normalize_listings,
    validate_data_quality,
)
from logger_config import setup_logging, log_scraping_session_start, log_scraping_session_end


def parse_iso_date(value: str) -> str:
    """Validate a YYYY-MM-DD date argument."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError("Expected date in YYYY-MM-DD format")
    return value


def slugify_path(value: str) -> str:
    """Convert a human location/path value into a URL slug path."""
    segments = [segment for segment in str(value).split('/') if segment.strip()]
    slugs = []
    for segment in segments:
        normalized = unicodedata.normalize('NFKD', segment)
        ascii_value = normalized.encode('ascii', 'ignore').decode('ascii')
        ascii_value = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_value)
        ascii_value = re.sub(r'-+', '-', ascii_value)
        slugs.append(ascii_value.strip('-').lower())
    return '/'.join(slugs)


def build_mubawab_display_url(args) -> str:
    """Build the Mubawab URL for logs before the scraper is created."""
    base_url = config.SOURCE_CONFIGS['mubawab']['base_url']
    if args.search_url:
        return urljoin(base_url, args.search_url)

    transaction = MubawabScraper.TRANSACTION_MAPPINGS[args.transaction]
    listing_slug = MubawabScraper.PROPERTY_SLUGS[args.property_type][transaction]
    if not args.location or args.location_level == 'sc':
        return f"{base_url}/fr/sc/{listing_slug}"

    location_slug = slugify_path(args.location)
    return f"{base_url}/fr/{args.location_level}/{location_slug}/{listing_slug}"


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Scrape real estate listings from Tunisian real estate sites',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--source',
        choices=sorted(config.SOURCE_CONFIGS.keys()),
        default=config.DEFAULT_SOURCE,
        help=f"Source to scrape (default: {config.DEFAULT_SOURCE})"
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=None,
        help='Maximum number of pages to scrape (default: unlimited)'
    )
    
    parser.add_argument(
        '--sample-size',
        type=int,
        default=None,
        help='Maximum number of listings to scrape (for testing)'
    )

    parser.add_argument(
        '--min-date-posted',
        '--date-posted-from',
        dest='min_date_posted',
        type=parse_iso_date,
        default=None,
        help='Keep only listings with date_posted on or after YYYY-MM-DD'
    )

    parser.add_argument(
        '--transaction',
        choices=['sale', 'rent', 'vente', 'location'],
        default=config.MUBAWAB_TRANSACTION,
        help='Mubawab transaction type (used only with --source mubawab)'
    )

    parser.add_argument(
        '--property-type',
        choices=[
            'logement', 'terrain', 'apartment', 'appartement', 'land',
            'house', 'maison', 'villa', 'commercial', 'local', 'office', 'bureau'
        ],
        default=config.MUBAWAB_PROPERTY_TYPE,
        help='Mubawab property type (used only with --source mubawab)'
    )

    parser.add_argument(
        '--location',
        default=None,
        help='Mubawab location name or slug, e.g. "La Marsa" or la-marsa'
    )

    parser.add_argument(
        '--location-level',
        choices=['sc', 'st', 'ct', 'cd', 'sd', 'is'],
        default=config.MUBAWAB_LOCATION_LEVEL,
        help='Mubawab location URL level: st, ct, cd, sd, is, or sc for all Tunisia'
    )

    parser.add_argument(
        '--search-url',
        default=None,
        help='Exact Mubawab search URL override, used only with --source mubawab'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Custom output directory (default: source-specific data directory)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode with verbose logging'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run scraper without saving data (for testing)'
    )
    
    parser.add_argument(
        '--use-playwright',
        action='store_true',
        help='Use Playwright for JavaScript-rendered content'
    )
    
    parser.add_argument(
        '--export-format',
        choices=['csv', 'json', 'both'],
        default='both',
        help='Output format (default: both)'
    )
    
    return parser.parse_args()


def update_config_from_args(args):
    """Update configuration based on command line arguments"""
    config.set_active_source(args.source)

    if args.max_pages:
        config.MAX_PAGES = args.max_pages
    
    if args.sample_size:
        config.SAMPLE_SIZE = args.sample_size

    if args.min_date_posted:
        config.MIN_DATE_POSTED = args.min_date_posted

    config.MUBAWAB_TRANSACTION = args.transaction
    config.MUBAWAB_PROPERTY_TYPE = args.property_type
    config.MUBAWAB_LOCATION = args.location
    config.MUBAWAB_LOCATION_LEVEL = args.location_level
    config.MUBAWAB_SEARCH_URL = args.search_url
    if args.source == 'mubawab':
        config.IMMOBILIER_URL = build_mubawab_display_url(args)
    
    if args.output_dir:
        config.set_output_dir(args.output_dir)
    
    if args.debug:
        config.DEBUG_MODE = True
        config.LOG_LEVEL = 'DEBUG'
        config.CONSOLE_LOG_LEVEL = 'DEBUG'
    
    if args.dry_run:
        config.DRY_RUN = True
    
    if args.use_playwright:
        config.USE_PLAYWRIGHT = True


def main():
    """Main execution function"""
    # Parse arguments and update config
    args = parse_arguments()
    update_config_from_args(args)
    
    # Setup logging
    logger = setup_logging()
    log_scraping_session_start()
    
    # Record start time
    start_time = time.time()
    
    try:
        # Initialize scraper
        logger.info(f"Initializing {config.SOURCE_DISPLAY_NAME} scraper...")
        if args.source == 'menzili':
            scraper = MenziliScraper()
        elif args.source == 'mubawab':
            scraper = MubawabScraper(
                transaction=args.transaction,
                property_type=args.property_type,
                location=args.location,
                location_level=args.location_level,
                search_url=args.search_url,
            )
        else:
            scraper = TayaraScraper()
        
        # Perform scraping
        logger.info("Starting scraping process...")
        listings = scraper.scrape_all(max_pages=args.max_pages)
        
        if not listings:
            logger.error("No listings were scraped. Exiting.")
            sys.exit(1)
        
        logger.info(f"Successfully scraped {len(listings)} listings")
        
        # Normalize data
        logger.info("Normalizing data...")
        normalized_listings = normalize_listings(listings)

        if config.MIN_DATE_POSTED:
            before_filter_count = len(normalized_listings)
            normalized_listings = filter_listings_by_min_date_posted(
                normalized_listings,
                config.MIN_DATE_POSTED,
            )
            logger.info(
                f"Date filter applied: {len(normalized_listings)}/"
                f"{before_filter_count} listings kept"
            )

            if not normalized_listings:
                logger.warning(
                    f"No listings matched date_posted >= {config.MIN_DATE_POSTED}. "
                    "Nothing to export."
                )
                return
        
        # Validate data quality
        logger.info("Validating data quality...")
        validation_result = validate_data_quality(normalized_listings)
        logger.info(f"Data quality score: {validation_result['quality_score']}/100")
        logger.info(f"Total issues found: {validation_result['total_issues']}")
        
        if not config.DRY_RUN:
            # Export data
            timestamp = datetime.now().strftime(config.TIMESTAMP_FORMAT)
            exporter = DataExporter(
                timestamp=timestamp,
                source=config.SOURCE_DOMAIN,
                filename_prefix=config.FILENAME_PREFIX,
            )
            
            if args.export_format in ['csv', 'both']:
                logger.info("Exporting to CSV...")
                csv_path = exporter.export_to_csv(normalized_listings)
                logger.info(f"CSV exported: {csv_path}")
            
            if args.export_format in ['json', 'both']:
                logger.info("Exporting to JSON...")
                json_path = exporter.export_to_json(normalized_listings)
                logger.info(f"JSON exported: {json_path}")
            
            # Generate and save summary report
            logger.info("Generating summary report...")
            report = exporter.generate_summary_report(normalized_listings)
            report['validation'] = validation_result
            if config.MIN_DATE_POSTED:
                report['filters'] = {'min_date_posted': config.MIN_DATE_POSTED}
            report_path = exporter.save_report(report)
            logger.info(f"Summary report saved: {report_path}")
            
            # Print summary to console
            print("\n" + "=" * 70)
            print("SCRAPING SUMMARY")
            print("=" * 70)
            print(f"Total listings: {report['total_listings']}")
            print(f"Quality score: {validation_result['quality_score']}/100")
            print(f"\nCategory distribution:")
            for category, count in report.get('category_distribution', {}).items():
                print(f"  {category}: {count}")
            print(f"\nTop cities:")
            for city, count in list(report.get('top_cities', {}).items())[:5]:
                print(f"  {city}: {count}")
            if 'price_stats' in report:
                print(f"\nPrice statistics (TND):")
                print(f"  Min: {report['price_stats']['min']:,.0f}")
                print(f"  Max: {report['price_stats']['max']:,.0f}")
                print(f"  Avg: {report['price_stats']['avg']:,.0f}")
            print("=" * 70)
        else:
            logger.info("DRY RUN: Data not saved")
        
    except KeyboardInterrupt:
        logger.warning("Scraping interrupted by user")
        sys.exit(1)
    
    except Exception as e:
        logger.exception(f"Unexpected error during scraping: {str(e)}")
        sys.exit(1)
    
    finally:
        # Log session end
        duration = time.time() - start_time
        log_scraping_session_end(
            listings_count=len(listings) if 'listings' in locals() else 0,
            errors_count=scraper.errors_encountered if 'scraper' in locals() else 0,
            duration=duration
        )
        
        logger.info("Scraper shutdown complete")


if __name__ == '__main__':
    main()
