#!/usr/bin/env python3
"""
Tunisian Real Estate Scraper - Main Entry Point

Usage:
    python main.py [options]

Options:
    --source NAME       Source to scrape: tayara or menzili
    --max-pages N       Limit scraping to N pages
    --sample-size N     Limit scraping to N listings (for testing)
    --output-dir PATH   Custom output directory
    --debug             Enable debug mode
    --dry-run           Run without saving data
    --use-playwright    Use Playwright for JavaScript-rendered content

Examples:
    # Scrape Menzili listings
    python main.py --source menzili --max-pages 2

    # Scrape first 5 pages
    python main.py --max-pages 5
    
    # Test with 10 listings
    python main.py --sample-size 10
    
    # Full scrape with debug logging
    python main.py --debug
"""

import argparse
import sys
from pathlib import Path
import time
from datetime import datetime

# Import project modules
import config
from scraper import TayaraScraper
from menzili_scraper import MenziliScraper
from data_exporter import DataExporter, normalize_listings, validate_data_quality
from logger_config import setup_logging, log_scraping_session_start, log_scraping_session_end


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
