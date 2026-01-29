"""
Database integration module

Handles storing scraped data in various databases:
- PostgreSQL
- MySQL
- SQLite

Provides ORM models and connection utilities
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, 
    Numeric, DateTime, Date, Boolean, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

import config

logger = logging.getLogger(__name__)

# SQLAlchemy Base
Base = declarative_base()


class Listing(Base):
    """
    SQLAlchemy model for real estate listings
    
    Represents a single scraped listing with all extracted fields
    """
    __tablename__ = 'listings'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Unique listing identifier
    listing_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Basic information
    title = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)
    
    # Price information
    price_numeric = Column(Numeric(precision=15, scale=2))
    currency = Column(String(10), default='TND')
    price_raw = Column(String(100))
    
    # Location
    location_raw = Column(String(500))
    city = Column(String(100), index=True)
    governorate = Column(String(100), index=True)
    neighborhood = Column(String(100))
    
    # Property details (flattened from criteria)
    surface = Column(Numeric(precision=10, scale=2))
    rooms = Column(Integer)
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    floor = Column(Integer)
    furnished = Column(Boolean)
    
    # Additional criteria as JSON
    criteria = Column(JSON)
    
    # Images
    image_urls = Column(JSON)
    image_count = Column(Integer, default=0)
    
    # Metadata
    date_posted = Column(Date)
    listing_url = Column(Text, nullable=False)
    scraped_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Listing(id={self.id}, listing_id='{self.listing_id}', title='{self.title[:30]}...')>"


class DatabaseManager:
    """
    Manages database connections and operations
    
    Supports multiple database backends via SQLAlchemy
    """
    
    def __init__(self, connection_string: str = None):
        """
        Initialize database manager
        
        Args:
            connection_string: SQLAlchemy connection string
                Examples:
                - PostgreSQL: postgresql://user:pass@localhost/dbname
                - MySQL: mysql+pymysql://user:pass@localhost/dbname
                - SQLite: sqlite:///path/to/database.db
        """
        if connection_string:
            self.connection_string = connection_string
        elif config.USE_DATABASE:
            self.connection_string = self._build_connection_string()
        else:
            # Default to SQLite in output directory
            db_path = config.OUTPUT_DIR / "tayara_listings.db"
            self.connection_string = f"sqlite:///{db_path}"
        
        logger.info(f"Initializing database connection: {self._safe_connection_string()}")
        
        self.engine = create_engine(self.connection_string, echo=config.DEBUG_MODE)
        self.Session = sessionmaker(bind=self.engine)
    
    def _build_connection_string(self) -> str:
        """Build connection string from config"""
        db_config = config.DATABASE_CONFIG
        db_type = config.DATABASE_TYPE
        
        if db_type == 'postgresql':
            return f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        elif db_type == 'mysql':
            return f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        elif db_type == 'sqlite':
            db_path = config.OUTPUT_DIR / f"{db_config['database']}.db"
            return f"sqlite:///{db_path}"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def _safe_connection_string(self) -> str:
        """Return connection string with password masked"""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', self.connection_string)
    
    def create_tables(self):
        """Create all tables if they don't exist"""
        logger.info("Creating database tables...")
        Base.metadata.create_all(self.engine)
        logger.info("Tables created successfully")
    
    def drop_tables(self):
        """Drop all tables (use with caution!)"""
        logger.warning("Dropping all tables...")
        Base.metadata.drop_all(self.engine)
        logger.warning("Tables dropped")
    
    def insert_listings(self, listings: List[Dict], update_existing: bool = True) -> int:
        """
        Insert listings into database
        
        Args:
            listings: List of listing dictionaries
            update_existing: If True, update existing records on conflict
            
        Returns:
            Number of records inserted/updated
        """
        session = self.Session()
        records_processed = 0
        
        try:
            for listing_dict in listings:
                # Prepare listing data
                listing_data = self._prepare_listing_data(listing_dict)
                
                if update_existing:
                    # Upsert logic (PostgreSQL)
                    if 'postgresql' in self.connection_string:
                        stmt = insert(Listing).values(**listing_data)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['listing_id'],
                            set_={
                                'price_numeric': stmt.excluded.price_numeric,
                                'description': stmt.excluded.description,
                                'criteria': stmt.excluded.criteria,
                                'image_urls': stmt.excluded.image_urls,
                                'scraped_at': stmt.excluded.scraped_at,
                                'updated_at': datetime.utcnow(),
                            }
                        )
                        session.execute(stmt)
                    else:
                        # For other databases, use merge
                        listing = session.query(Listing).filter_by(
                            listing_id=listing_data['listing_id']
                        ).first()
                        
                        if listing:
                            # Update existing
                            for key, value in listing_data.items():
                                setattr(listing, key, value)
                            listing.updated_at = datetime.utcnow()
                        else:
                            # Insert new
                            listing = Listing(**listing_data)
                            session.add(listing)
                else:
                    # Insert only (skip if exists)
                    existing = session.query(Listing).filter_by(
                        listing_id=listing_data['listing_id']
                    ).first()
                    
                    if not existing:
                        listing = Listing(**listing_data)
                        session.add(listing)
                
                records_processed += 1
            
            session.commit()
            logger.info(f"Successfully processed {records_processed} listings")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error inserting listings: {str(e)}")
            raise
        finally:
            session.close()
        
        return records_processed
    
    def _prepare_listing_data(self, listing_dict: Dict) -> Dict:
        """
        Prepare listing dictionary for database insertion
        
        Handles:
        - Field mapping
        - Type conversions
        - Nested structure flattening
        """
        # Parse scraped_at timestamp
        scraped_at = listing_dict.get('scraped_at')
        if isinstance(scraped_at, str):
            scraped_at = datetime.fromisoformat(scraped_at)
        
        # Parse date_posted
        date_posted = listing_dict.get('date_posted')
        if isinstance(date_posted, str):
            try:
                date_posted = datetime.fromisoformat(date_posted).date()
            except (ValueError, AttributeError):
                date_posted = None
        
        # Extract criteria fields
        criteria = listing_dict.get('criteria', {})
        
        # Prepare data
        data = {
            'listing_id': listing_dict.get('listing_id'),
            'title': listing_dict.get('title'),
            'description': listing_dict.get('description'),
            'category': listing_dict.get('category'),
            'price_numeric': listing_dict.get('price_numeric'),
            'currency': listing_dict.get('currency', 'TND'),
            'price_raw': listing_dict.get('price_raw'),
            'location_raw': listing_dict.get('location_raw'),
            'city': listing_dict.get('city'),
            'governorate': listing_dict.get('governorate'),
            'neighborhood': listing_dict.get('neighborhood'),
            'surface': listing_dict.get('surface') or criteria.get('surface'),
            'rooms': listing_dict.get('rooms') or criteria.get('rooms'),
            'bedrooms': listing_dict.get('bedrooms') or criteria.get('bedrooms'),
            'bathrooms': listing_dict.get('bathrooms') or criteria.get('bathrooms'),
            'floor': criteria.get('floor'),
            'furnished': criteria.get('furnished'),
            'criteria': criteria,  # Store full criteria as JSON
            'image_urls': listing_dict.get('image_urls', []),
            'image_count': listing_dict.get('image_count', 0),
            'date_posted': date_posted,
            'listing_url': listing_dict.get('listing_url'),
            'scraped_at': scraped_at,
        }
        
        return data
    
    def get_listing_by_id(self, listing_id: str) -> Optional[Listing]:
        """Retrieve a listing by its ID"""
        session = self.Session()
        try:
            return session.query(Listing).filter_by(listing_id=listing_id).first()
        finally:
            session.close()
    
    def get_recent_listings(self, limit: int = 100) -> List[Listing]:
        """Get most recently scraped listings"""
        session = self.Session()
        try:
            return session.query(Listing).order_by(
                Listing.scraped_at.desc()
            ).limit(limit).all()
        finally:
            session.close()
    
    def get_listings_by_city(self, city: str) -> List[Listing]:
        """Get all listings for a specific city"""
        session = self.Session()
        try:
            return session.query(Listing).filter_by(city=city).all()
        finally:
            session.close()
    
    def count_listings(self) -> int:
        """Get total number of listings in database"""
        session = self.Session()
        try:
            return session.query(Listing).count()
        finally:
            session.close()
    
    def get_statistics(self) -> Dict:
        """
        Get database statistics
        
        Returns summary statistics about stored listings
        """
        session = self.Session()
        try:
            from sqlalchemy import func
            
            stats = {
                'total_listings': session.query(Listing).count(),
                'listings_by_category': dict(
                    session.query(Listing.category, func.count(Listing.id))
                    .group_by(Listing.category).all()
                ),
                'listings_by_city': dict(
                    session.query(Listing.city, func.count(Listing.id))
                    .group_by(Listing.city)
                    .order_by(func.count(Listing.id).desc())
                    .limit(10).all()
                ),
                'avg_price': session.query(func.avg(Listing.price_numeric)).scalar(),
                'latest_scrape': session.query(func.max(Listing.scraped_at)).scalar(),
            }
            
            return stats
        finally:
            session.close()


# Convenience function
def save_to_database(listings: List[Dict], connection_string: str = None) -> int:
    """
    Convenience function to save listings to database
    
    Args:
        listings: List of listing dictionaries
        connection_string: Optional custom connection string
        
    Returns:
        Number of records saved
    """
    db = DatabaseManager(connection_string)
    db.create_tables()
    return db.insert_listings(listings)


if __name__ == '__main__':
    # Example usage
    print("Database Integration Module")
    print("=" * 50)
    
    # Create manager with SQLite (for testing)
    db = DatabaseManager()
    print(f"Connection: {db._safe_connection_string()}")
    
    # Create tables
    db.create_tables()
    print("Tables created")
    
    # Get statistics
    stats = db.get_statistics()
    print(f"\nDatabase Statistics:")
    print(f"Total listings: {stats['total_listings']}")
    print(f"Latest scrape: {stats['latest_scrape']}")
