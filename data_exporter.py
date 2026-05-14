"""
Data processing and export utilities

Handles:
- Data normalization
- CSV export
- JSON export
- Data quality reporting
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import logging

import config

logger = logging.getLogger(__name__)


def has_required_field(listing: Dict, field: str) -> bool:
    """Check required fields, accepting normalized price fields for legacy config."""
    if field == 'price':
        has_numeric_price = listing.get('price_numeric') not in [None, '', 'N/A']
        has_raw_price = listing.get('price_raw') not in [None, '', 'N/A']
        return has_numeric_price or has_raw_price
    return bool(listing.get(field) and listing.get(field) != 'N/A')


class DataExporter:
    """
    Handles exporting scraped data to various formats
    
    Supports:
    - CSV with proper encoding for Arabic/French text
    - JSON with pretty printing
    - Data normalization before export
    """
    
    def __init__(self, timestamp: str = None, source: str = None, filename_prefix: str = None):
        """
        Initialize exporter with timestamp for file naming
        
        Args:
            timestamp: Custom timestamp string, or None to generate current
            source: Source domain to write into JSON metadata
            filename_prefix: Prefix used in exported filenames
        """
        self.timestamp = timestamp or datetime.now().strftime(config.TIMESTAMP_FORMAT)
        self.source = source or getattr(config, 'SOURCE_DOMAIN', 'tayara.tn')
        self.filename_prefix = filename_prefix or getattr(config, 'FILENAME_PREFIX', 'tayara')
        
    def export_to_csv(self, listings: List[Dict], output_dir: Path = None) -> Path:
        """
        Export listings to CSV file
        
        Args:
            listings: List of listing dictionaries
            output_dir: Directory to save CSV (defaults to processed data dir)
            
        Returns:
            Path to created CSV file
        """
        if not listings:
            logger.warning("No listings to export to CSV")
            return None
        
        output_dir = output_dir or config.PROCESSED_DATA_DIR
        filename = config.get_output_filename(
            config.CSV_FILENAME_TEMPLATE,
            self.timestamp,
            source=self.filename_prefix,
        )
        filepath = output_dir / filename
        
        # Flatten nested criteria dictionary for CSV
        flattened_listings = [self._flatten_listing(listing) for listing in listings]
        
        # Get all unique field names across all listings
        all_fields = set()
        for listing in flattened_listings:
            all_fields.update(listing.keys())
        
        # Define field order (important fields first, then alphabetical)
        priority_fields = [
            'listing_id', 'title', 'price_numeric', 'currency', 'price_raw',
            'category', 'city', 'governorate', 'neighborhood', 'location_raw',
            'surface', 'rooms', 'bedrooms', 'bathrooms', 'floor', 'furnished',
            'description', 'date_posted', 'image_count', 'listing_url', 'scraped_at'
        ]
        
        # Remaining fields alphabetically
        remaining_fields = sorted(all_fields - set(priority_fields))
        fieldnames = [f for f in priority_fields if f in all_fields] + remaining_fields
        
        # Write CSV with UTF-8 encoding
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(flattened_listings)
        
        logger.info(f"Exported {len(listings)} listings to CSV: {filepath}")
        return filepath
    
    def export_to_json(self, listings: List[Dict], output_dir: Path = None) -> Path:
        """
        Export listings to JSON file
        
        Args:
            listings: List of listing dictionaries
            output_dir: Directory to save JSON (defaults to processed data dir)
            
        Returns:
            Path to created JSON file
        """
        if not listings:
            logger.warning("No listings to export to JSON")
            return None
        
        output_dir = output_dir or config.PROCESSED_DATA_DIR
        filename = config.get_output_filename(
            config.JSON_FILENAME_TEMPLATE,
            self.timestamp,
            source=self.filename_prefix,
        )
        filepath = output_dir / filename
        
        # Create metadata
        export_data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'total_listings': len(listings),
                'source': self.source,
                'category': 'immobilier',
            },
            'listings': listings
        }
        
        # Write JSON with pretty printing
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, ensure_ascii=False, indent=2)
        
        logger.info(f"Exported {len(listings)} listings to JSON: {filepath}")
        return filepath
    
    def _flatten_listing(self, listing: Dict) -> Dict:
        """
        Flatten nested structures for CSV export
        
        Handles:
        - criteria dictionary → individual columns with prefix
        - image_urls list → JSON string or count
        """
        flattened = listing.copy()
        
        # Flatten criteria dictionary
        if 'criteria' in flattened and isinstance(flattened['criteria'], dict):
            criteria = flattened.pop('criteria')
            for key, value in criteria.items():
                # Add prefix to avoid column name conflicts
                # Only add if not already in top level
                criteria_key = f"criteria_{key}"
                if key not in flattened:
                    flattened[criteria_key] = value
        
        # Convert image URLs list to JSON string for CSV
        if 'image_urls' in flattened and isinstance(flattened['image_urls'], list):
            flattened['image_urls'] = json.dumps(flattened['image_urls'], ensure_ascii=False)
        
        return flattened
    
    def generate_summary_report(self, listings: List[Dict]) -> Dict:
        """
        Generate summary statistics and data quality report
        
        Returns:
            Dictionary containing summary statistics
        """
        if not listings:
            return {'error': 'No listings to analyze'}
        
        report = {
            'total_listings': len(listings),
            'timestamp': datetime.now().isoformat(),
        }
        
        # Field completeness
        field_completeness = {}
        for field in ['title', 'price_numeric', 'category', 'location_raw', 'description', 'date_posted']:
            non_null_count = sum(1 for l in listings if l.get(field) and l.get(field) != 'N/A')
            field_completeness[field] = {
                'count': non_null_count,
                'percentage': round(non_null_count / len(listings) * 100, 2)
            }
        report['field_completeness'] = field_completeness
        
        # Price statistics
        prices = [l['price_numeric'] for l in listings if l.get('price_numeric')]
        if prices:
            report['price_stats'] = {
                'min': min(prices),
                'max': max(prices),
                'avg': round(sum(prices) / len(prices), 2),
                'median': sorted(prices)[len(prices) // 2],
            }
        
        # Category distribution
        categories = {}
        for listing in listings:
            cat = listing.get('category', 'Unknown')
            categories[cat] = categories.get(cat, 0) + 1
        report['category_distribution'] = categories
        
        # Location distribution (top 10)
        cities = {}
        for listing in listings:
            city = listing.get('city', 'Unknown')
            if city:
                cities[city] = cities.get(city, 0) + 1
        report['top_cities'] = dict(sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Image statistics
        total_images = sum(l.get('image_count', 0) for l in listings)
        listings_with_images = sum(1 for l in listings if l.get('image_count', 0) > 0)
        report['image_stats'] = {
            'total_images': total_images,
            'listings_with_images': listings_with_images,
            'avg_images_per_listing': round(total_images / len(listings), 2) if listings else 0,
        }
        
        return report
    
    def save_report(self, report: Dict, output_dir: Path = None) -> Path:
        """Save summary report to JSON file"""
        output_dir = output_dir or config.PROCESSED_DATA_DIR
        filename = f"summary_report_{self.filename_prefix}_{self.timestamp}.json"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved summary report: {filepath}")
        return filepath


def normalize_listings(listings: List[Dict]) -> List[Dict]:
    """
    Post-processing normalization of listing data
    
    Applies:
    - Data type conversions
    - Field standardization
    - Deduplication
    """
    normalized = []
    seen_ids = set()
    
    for listing in listings:
        # Skip duplicates based on listing_id
        listing_id = listing.get('listing_id')
        if listing_id in seen_ids:
            logger.warning(f"Duplicate listing_id found: {listing_id}")
            continue
        seen_ids.add(listing_id)
        
        # Normalize price
        if listing.get('price_numeric'):
            listing['price_numeric'] = float(listing['price_numeric'])
        
        # Normalize dates to ISO format (already done in scraper, but verify)
        if listing.get('date_posted'):
            # Ensure it's in ISO format
            pass  # Already handled in scraper
        
        # Normalize boolean fields
        for bool_field in ['furnished', 'garage', 'elevator', 'pool', 'garden']:
            if bool_field in listing.get('criteria', {}):
                listing['criteria'][bool_field] = bool(listing['criteria'][bool_field])
        
        # Ensure image_urls is a list
        if not isinstance(listing.get('image_urls'), list):
            listing['image_urls'] = []
        
        normalized.append(listing)
    
    logger.info(f"Normalized {len(normalized)} listings (removed {len(listings) - len(normalized)} duplicates)")
    return normalized


def validate_data_quality(listings: List[Dict]) -> Dict:
    """
    Validate data quality and return issues found
    
    Returns:
        Dictionary with validation results and issues
    """
    issues = {
        'missing_required_fields': [],
        'invalid_prices': [],
        'missing_images': [],
        'incomplete_location': [],
    }
    
    for idx, listing in enumerate(listings):
        listing_id = listing.get('listing_id', f'index_{idx}')
        
        # Check required fields
        for field in config.MIN_REQUIRED_FIELDS:
            if not has_required_field(listing, field):
                issues['missing_required_fields'].append({
                    'listing_id': listing_id,
                    'field': field
                })
        
        # Check price validity
        if listing.get('price_numeric') is not None:
            if listing['price_numeric'] <= 0:
                issues['invalid_prices'].append({
                    'listing_id': listing_id,
                    'price': listing['price_numeric']
                })
        
        # Check for listings without images
        if listing.get('image_count', 0) == 0:
            issues['missing_images'].append(listing_id)
        
        # Check location completeness
        if not listing.get('city') or not listing.get('governorate'):
            issues['incomplete_location'].append(listing_id)
    
    # Summary
    validation_result = {
        'total_issues': sum(len(v) if isinstance(v, list) else 0 for v in issues.values()),
        'issues': issues,
        'quality_score': calculate_quality_score(listings, issues),
    }
    
    return validation_result


def calculate_quality_score(listings: List[Dict], issues: Dict) -> float:
    """
    Calculate overall data quality score (0-100)
    
    Based on:
    - Field completeness
    - Data validity
    - Image availability
    """
    if not listings:
        return 0.0
    
    total_listings = len(listings)
    
    # Penalties
    penalties = 0
    penalties += len(issues['missing_required_fields']) * 2  # High penalty
    penalties += len(issues['invalid_prices']) * 1
    penalties += len(issues['missing_images']) * 0.5  # Lower penalty
    penalties += len(issues['incomplete_location']) * 1
    
    # Calculate score (max 100)
    max_possible_penalties = total_listings * 10  # Arbitrary max
    score = max(0, 100 - (penalties / max_possible_penalties * 100))
    
    return round(score, 2)
