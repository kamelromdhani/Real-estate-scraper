"""
Apache Airflow DAG for Tayara.tn Scraper

This DAG demonstrates how to integrate the scraper into a data pipeline:
- Scheduled daily scraping
- Data validation
- Database loading
- Alert on failures

Usage:
    Place this file in your Airflow DAGs folder (typically ~/airflow/dags/)
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.email import send_email

# Import scraper modules (adjust path as needed)
import sys
sys.path.append('/path/to/scraper/directory')
from scraper import TayaraScraper
from data_exporter import DataExporter, normalize_listings, validate_data_quality
import config


# Default DAG arguments
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email': ['alerts@yourcompany.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def scrape_tayara(**context):
    """
    Scrape Tayara.tn listings
    
    Returns:
        Number of listings scraped
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting Tayara scraping task")
    
    # Initialize scraper
    scraper = TayaraScraper()
    
    # Perform scraping (limit to reasonable number for daily run)
    listings = scraper.scrape_all(max_pages=10)
    
    if not listings:
        raise ValueError("No listings scraped - check website availability")
    
    # Normalize data
    normalized_listings = normalize_listings(listings)
    
    # Export to JSON for next task
    timestamp = datetime.now().strftime(config.TIMESTAMP_FORMAT)
    exporter = DataExporter(timestamp=timestamp)
    json_path = exporter.export_to_json(normalized_listings)
    
    # Push data path to XCom for next tasks
    context['task_instance'].xcom_push(key='listings_json_path', value=str(json_path))
    context['task_instance'].xcom_push(key='listings_count', value=len(normalized_listings))
    
    logger.info(f"Scraped {len(normalized_listings)} listings")
    return len(normalized_listings)


def validate_data_task(**context):
    """
    Validate scraped data quality
    
    Raises:
        ValueError if quality score is below threshold
    """
    logger = logging.getLogger(__name__)
    
    # Get data path from previous task
    ti = context['task_instance']
    json_path = ti.xcom_pull(key='listings_json_path', task_ids='scrape_listings')
    
    # Load data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    listings = data['listings']
    
    # Validate
    validation_result = validate_data_quality(listings)
    quality_score = validation_result['quality_score']
    
    logger.info(f"Data quality score: {quality_score}/100")
    
    # Push validation result
    ti.xcom_push(key='quality_score', value=quality_score)
    ti.xcom_push(key='validation_result', value=validation_result)
    
    # Fail if quality is too low
    if quality_score < 70:
        raise ValueError(f"Data quality score ({quality_score}) below threshold (70)")
    
    return quality_score


def load_to_database(**context):
    """
    Load validated data into PostgreSQL database
    """
    logger = logging.getLogger(__name__)
    
    # Get data path
    ti = context['task_instance']
    json_path = ti.xcom_pull(key='listings_json_path', task_ids='scrape_listings')
    
    # Load data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    listings = data['listings']
    
    # Connect to database
    hook = PostgresHook(postgres_conn_id='tayara_db')
    conn = hook.get_conn()
    cursor = conn.cursor()
    
    # Insert listings (example - adjust to your schema)
    insert_query = """
        INSERT INTO listings (
            listing_id, title, price_numeric, currency, category,
            city, governorate, description, date_posted, listing_url,
            scraped_at
        ) VALUES (
            %(listing_id)s, %(title)s, %(price_numeric)s, %(currency)s, %(category)s,
            %(city)s, %(governorate)s, %(description)s, %(date_posted)s, %(listing_url)s,
            %(scraped_at)s
        )
        ON CONFLICT (listing_id) DO UPDATE SET
            price_numeric = EXCLUDED.price_numeric,
            description = EXCLUDED.description,
            scraped_at = EXCLUDED.scraped_at
    """
    
    records_inserted = 0
    for listing in listings:
        try:
            cursor.execute(insert_query, listing)
            records_inserted += 1
        except Exception as e:
            logger.error(f"Error inserting listing {listing.get('listing_id')}: {str(e)}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    logger.info(f"Inserted/updated {records_inserted} listings in database")
    return records_inserted


def send_success_notification(**context):
    """Send email notification on successful pipeline run"""
    ti = context['task_instance']
    listings_count = ti.xcom_pull(key='listings_count', task_ids='scrape_listings')
    quality_score = ti.xcom_pull(key='quality_score', task_ids='validate_data')
    
    subject = f"Tayara Scraper Success - {listings_count} listings"
    body = f"""
    The Tayara.tn scraping pipeline completed successfully.
    
    Summary:
    - Listings scraped: {listings_count}
    - Data quality score: {quality_score}/100
    - Execution date: {context['execution_date']}
    
    Dashboard: https://your-dashboard.com/tayara
    """
    
    send_email(
        to=['data-team@yourcompany.com'],
        subject=subject,
        html_content=body
    )


# Define DAG
with DAG(
    'tayara_scraper_pipeline',
    default_args=default_args,
    description='Daily scraping of Tayara.tn real estate listings',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    catchup=False,
    tags=['scraping', 'real-estate', 'tayara'],
) as dag:
    
    # Task 1: Scrape listings
    scrape_task = PythonOperator(
        task_id='scrape_listings',
        python_callable=scrape_tayara,
        provide_context=True,
    )
    
    # Task 2: Validate data quality
    validate_task = PythonOperator(
        task_id='validate_data',
        python_callable=validate_data_task,
        provide_context=True,
    )
    
    # Task 3: Load to database
    load_task = PythonOperator(
        task_id='load_to_database',
        python_callable=load_to_database,
        provide_context=True,
    )
    
    # Task 4: Create database table if not exists
    create_table_task = PostgresOperator(
        task_id='create_table',
        postgres_conn_id='tayara_db',
        sql="""
            CREATE TABLE IF NOT EXISTS listings (
                id SERIAL PRIMARY KEY,
                listing_id VARCHAR(50) UNIQUE NOT NULL,
                title TEXT NOT NULL,
                price_numeric NUMERIC,
                currency VARCHAR(10),
                category VARCHAR(50),
                city VARCHAR(100),
                governorate VARCHAR(100),
                neighborhood VARCHAR(100),
                description TEXT,
                date_posted DATE,
                listing_url TEXT NOT NULL,
                scraped_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_listing_id ON listings(listing_id);
            CREATE INDEX IF NOT EXISTS idx_city ON listings(city);
            CREATE INDEX IF NOT EXISTS idx_category ON listings(category);
            CREATE INDEX IF NOT EXISTS idx_scraped_at ON listings(scraped_at);
        """,
    )
    
    # Task 5: Export to CSV (for backup/analysis)
    export_csv_task = BashOperator(
        task_id='export_to_csv',
        bash_command='python /path/to/scraper/main.py --export-format csv',
    )
    
    # Task 6: Send success notification
    notify_task = PythonOperator(
        task_id='send_notification',
        python_callable=send_success_notification,
        provide_context=True,
    )
    
    # Define task dependencies
    create_table_task >> scrape_task >> validate_task >> load_task >> export_csv_task >> notify_task


"""
Additional Airflow Integration Notes:

1. Setup Airflow Connection:
   - Go to Admin > Connections in Airflow UI
   - Create connection with ID 'tayara_db':
     * Conn Type: Postgres
     * Host: your-db-host
     * Schema: tayara_db
     * Login: your-username
     * Password: your-password
     * Port: 5432

2. Monitoring:
   - Check DAG runs in Airflow UI
   - Set up alerts for failures
   - Use Airflow's built-in retry mechanism

3. Scaling:
   - Use CeleryExecutor or KubernetesExecutor for parallel processing
   - Consider splitting large scrapes into smaller chunks
   - Implement incremental loading (only new/updated listings)

4. Best Practices:
   - Use Airflow Variables for configuration
   - Implement idempotency (safe to retry)
   - Add data quality sensors
   - Archive old data periodically
"""
