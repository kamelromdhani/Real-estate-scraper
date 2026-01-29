#!/usr/bin/env python3
"""
Quick Start Example - Tayara.tn Scraper

This script demonstrates basic usage with a small sample
Perfect for testing and learning the scraper
"""

import sys
from pathlib import Path

# Import scraper modules
from scraper import TayaraScraper
from data_exporter import DataExporter, normalize_listings, validate_data_quality
from database import DatabaseManager
from logger_config import setup_logging
import config


def example_basic_scraping():
    """
    Example 1: Basic scraping with 5 listings
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Scraping (5 listings)")
    print("=" * 70)
    
    # Configure for testing
    config.SAMPLE_SIZE = 100
    config.DEBUG_MODE = False
    
    # Initialize scraper
    scraper = TayaraScraper()
    
    # Scrape listings
    print("Scraping 5 sample listings...")
    listings = scraper.scrape_all(max_pages=1)
    
    if not listings:
        print("❌ No listings scraped")
        return None
    
    print(f"✓ Successfully scraped {len(listings)} listings")
    
    # Show first listing
    if listings:
        first = listings[0]
        print(f"\nFirst listing:")
        print(f"  Title: {first.get('title', 'N/A')[:60]}...")
        print(f"  Price: {first.get('price_numeric', 'N/A')} {first.get('currency', 'TND')}")
        print(f"  Location: {first.get('city', 'N/A')}, {first.get('governorate', 'N/A')}")
        print(f"  URL: {first.get('listing_url', 'N/A')}")
    
    return listings


def example_data_export(listings):
    """
    Example 2: Export data to CSV and JSON
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Data Export")
    print("=" * 70)
    
    if not listings:
        print("⚠️  No listings to export")
        return
    
    # Normalize data
    normalized = normalize_listings(listings)
    
    # Create exporter
    exporter = DataExporter()
    
    # Export to CSV
    print("Exporting to CSV...")
    csv_path = exporter.export_to_csv(normalized)
    print(f"✓ CSV saved: {csv_path}")
    
    # Export to JSON
    print("Exporting to JSON...")
    json_path = exporter.export_to_json(normalized)
    print(f"✓ JSON saved: {json_path}")
    
    return normalized


def example_data_quality(listings):
    """
    Example 3: Data quality validation
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Data Quality Check")
    print("=" * 70)
    
    if not listings:
        print("⚠️  No listings to validate")
        return
    
    # Validate data
    validation_result = validate_data_quality(listings)
    
    print(f"Quality Score: {validation_result['quality_score']}/100")
    print(f"Total Issues: {validation_result['total_issues']}")
    
    # Show issues by type
    issues = validation_result['issues']
    print("\nIssue Breakdown:")
    print(f"  Missing required fields: {len(issues['missing_required_fields'])}")
    print(f"  Invalid prices: {len(issues['invalid_prices'])}")
    print(f"  Missing images: {len(issues['missing_images'])}")
    print(f"  Incomplete location: {len(issues['incomplete_location'])}")
    
    return validation_result


def example_summary_report(listings):
    """
    Example 4: Generate summary report
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Summary Report")
    print("=" * 70)
    
    if not listings:
        print("⚠️  No listings for report")
        return
    
    # Generate report
    exporter = DataExporter()
    report = exporter.generate_summary_report(listings)
    
    print(f"Total Listings: {report['total_listings']}")
    
    # Field completeness
    print("\nField Completeness:")
    for field, stats in report['field_completeness'].items():
        print(f"  {field}: {stats['percentage']}%")
    
    # Category distribution
    if 'category_distribution' in report:
        print("\nCategory Distribution:")
        for category, count in report['category_distribution'].items():
            print(f"  {category}: {count}")
    
    # Price stats
    if 'price_stats' in report:
        print("\nPrice Statistics:")
        print(f"  Min: {report['price_stats']['min']:,.0f} TND")
        print(f"  Max: {report['price_stats']['max']:,.0f} TND")
        print(f"  Avg: {report['price_stats']['avg']:,.0f} TND")
    
    return report


def example_database_storage(listings):
    """
    Example 5: Store in SQLite database
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Database Storage")
    print("=" * 70)
    
    if not listings:
        print("⚠️  No listings to store")
        return
    
    # Create database manager (uses SQLite by default)
    db = DatabaseManager()
    
    print("Creating database tables...")
    db.create_tables()
    
    print(f"Inserting {len(listings)} listings...")
    count = db.insert_listings(listings)
    print(f"✓ Inserted {count} records")
    
    # Get statistics
    stats = db.get_statistics()
    print(f"\nDatabase Statistics:")
    print(f"  Total listings: {stats['total_listings']}")
    print(f"  Average price: {stats['avg_price']:,.2f} TND" if stats['avg_price'] else "  Average price: N/A")
    
    # Show recent listings
    recent = db.get_recent_listings(limit=3)
    print(f"\nRecent Listings (top 3):")
    for listing in recent:
        print(f"  - {listing.title[:50]}...")
    
    return db


def example_advanced_scraping():
    """
    Example 6: Advanced scraping with custom config
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Advanced Scraping Configuration")
    print("=" * 70)
    
    # Customize config
    original_delay_min = config.REQUEST_DELAY_MIN
    original_delay_max = config.REQUEST_DELAY_MAX
    
    config.REQUEST_DELAY_MIN = 1.0  # Faster for testing
    config.REQUEST_DELAY_MAX = 2.0
    config.SAMPLE_SIZE = 10
    config.SAVE_HTML_SNAPSHOTS = True  # Save HTML for debugging
    
    print("Configuration:")
    print(f"  Request delay: {config.REQUEST_DELAY_MIN}-{config.REQUEST_DELAY_MAX}s")
    print(f"  Sample size: {config.SAMPLE_SIZE}")
    print(f"  Save HTML: {config.SAVE_HTML_SNAPSHOTS}")
    
    # Scrape
    scraper = TayaraScraper()
    listings = scraper.scrape_all(max_pages=2)
    
    print(f"✓ Scraped {len(listings)} listings from 2 pages")
    
    # Restore original config
    config.REQUEST_DELAY_MIN = original_delay_min
    config.REQUEST_DELAY_MAX = original_delay_max
    config.SAVE_HTML_SNAPSHOTS = False
    
    return listings


def run_all_examples():
    """
    Run all examples in sequence
    """
    print("\n" + "=" * 70)
    print("TAYARA.TN SCRAPER - QUICK START EXAMPLES")
    print("=" * 70)
    print("\nThis script demonstrates the scraper's capabilities")
    print("Press Ctrl+C to stop at any time\n")
    
    try:
        # Setup logging
        setup_logging()
        
        # Example 1: Basic scraping
        listings = example_basic_scraping()
        
        if listings:
            # Example 2: Export data
            normalized = example_data_export(listings)
            
            # Example 3: Data quality
            example_data_quality(normalized)
            
            # Example 4: Summary report
            example_summary_report(normalized)
            
            # Example 5: Database storage
            example_database_storage(normalized)
        
        # Example 6: Advanced config (separate scrape)
        # example_advanced_scraping()
        
        print("\n" + "=" * 70)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Check output files in: data/tayara_scrape/")
        print("2. Review the README.md for full documentation")
        print("3. Customize config.py for your needs")
        print("4. Run 'python main.py' for full scraping")
        print("=" * 70 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Examples interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    # Check if user wants to run specific example
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        
        if example_num == '1':
            listings = example_basic_scraping()
        elif example_num == '2':
            listings = example_basic_scraping()
            example_data_export(listings)
        elif example_num == '3':
            listings = example_basic_scraping()
            example_data_quality(listings)
        elif example_num == '4':
            listings = example_basic_scraping()
            example_summary_report(listings)
        elif example_num == '5':
            listings = example_basic_scraping()
            example_database_storage(listings)
        elif example_num == '6':
            example_advanced_scraping()
        else:
            print(f"Unknown example: {example_num}")
            print("Usage: python example.py [1-6]")
            print("  Or run without arguments for all examples")
    else:
        # Run all examples
        run_all_examples()
