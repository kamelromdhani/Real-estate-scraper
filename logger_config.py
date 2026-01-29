"""
Logging configuration for the scraper

Sets up both console and file logging with appropriate formatting
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

import config


def setup_logging(log_filename: str = None) -> logging.Logger:
    """
    Configure logging for the application
    
    Args:
        log_filename: Optional custom log filename
        
    Returns:
        Configured root logger
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT
    )
    
    simple_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # Console handler
    if config.CONSOLE_LOG_ENABLED:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.CONSOLE_LOG_LEVEL))
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if config.FILE_LOG_ENABLED:
        if not log_filename:
            timestamp = datetime.now().strftime(config.TIMESTAMP_FORMAT)
            log_filename = config.get_output_filename(config.LOG_FILENAME_TEMPLATE, timestamp)
        
        log_filepath = config.LOGS_DIR / log_filename
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setLevel(getattr(logging, config.FILE_LOG_LEVEL))
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"Logging to file: {log_filepath}")
    
    return logger


def log_scraping_session_start():
    """Log the start of a scraping session with configuration"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 70)
    logger.info("TAYARA.TN SCRAPING SESSION STARTED")
    logger.info("=" * 70)
    logger.info(f"Target URL: {config.IMMOBILIER_URL}")
    logger.info(f"Max pages: {config.MAX_PAGES or 'Unlimited'}")
    logger.info(f"Sample size: {config.SAMPLE_SIZE or 'Unlimited'}")
    logger.info(f"Request delay: {config.REQUEST_DELAY_MIN}-{config.REQUEST_DELAY_MAX}s")
    logger.info(f"Output directory: {config.OUTPUT_DIR}")
    logger.info(f"Debug mode: {config.DEBUG_MODE}")
    logger.info(f"Dry run: {config.DRY_RUN}")
    logger.info("=" * 70)


def log_scraping_session_end(listings_count: int, errors_count: int, duration: float):
    """Log the end of a scraping session with summary"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 70)
    logger.info("TAYARA.TN SCRAPING SESSION COMPLETED")
    logger.info("=" * 70)
    logger.info(f"Total listings scraped: {listings_count}")
    logger.info(f"Errors encountered: {errors_count}")
    logger.info(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    logger.info(f"Average time per listing: {duration/listings_count:.2f}s" if listings_count > 0 else "N/A")
    logger.info("=" * 70)
