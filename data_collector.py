#!/usr/bin/env python3
"""
Automated Data Collector for Hydrological Dashboard
Runs every 6 hours to fetch data from FFD APIs and store in local database
"""

import requests
import sqlite3
import json
import time
import schedule
import logging
from datetime import datetime, timezone
from pathlib import Path

# Configuration
DB_PATH = Path(__file__).parent / "backend" / "hydro_history.db"
LOG_PATH = Path(__file__).parent / "data_collector.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize the database with required tables"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create telemetry_history table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                inflow_discharge REAL,
                outflow_discharge REAL,
                inflow_trend TEXT,
                outflow_trend TEXT,
                fetched_at TEXT NOT NULL,
                UNIQUE(name, type, fetched_at)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        return False

def fetch_ffd_data():
    """Fetch data from FFD APIs"""
    try:
        logger.info("🚀 Starting data collection from FFD APIs...")
        
        # Fetch dams data
        logger.info("📡 Fetching dams data...")
        dams_response = requests.get('https://ffd.gov.pk/api/dams', timeout=60)
        
        # Fetch headworks data  
        logger.info("📡 Fetching headworks data...")
        headworks_response = requests.get('https://ffd.gov.pk/api/headworks', timeout=60)
        
        if dams_response.ok and headworks_response.ok:
            dams_data = dams_response.json()
            headworks_data = headworks_response.json()
            
            logger.info(f"✅ APIs responded successfully")
            logger.info(f"   - Dams: {len(dams_data.get('dams', []))} items")
            logger.info(f"   - Headworks: {len(headworks_data.get('headworks', []))} items")
            
            return dams_data, headworks_data
        else:
            logger.error(f"❌ API Error: Dams {dams_response.status_code}, Headworks {headworks_response.status_code}")
            return None, None
            
    except requests.exceptions.Timeout:
        logger.error("❌ API timeout - FFD servers may be slow")
        return None, None
    except requests.exceptions.ConnectionError:
        logger.error("❌ Connection error - Check internet connection")
        return None, None
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching data: {str(e)}")
        return None, None

def calculate_trend(current, previous):
    """Calculate trend direction based on current and previous values"""
    if current is None or previous is None:
        return 'stable'
    
    try:
        # Handle string values with commas
        if isinstance(current, str):
            current = float(current.replace(',', ''))
        if isinstance(previous, str):
            previous = float(previous.replace(',', ''))
            
        diff = current - previous
        if abs(diff) < 0.01:  # Very small change
            return 'stable'
        elif diff > 0:
            return 'increasing'
        else:
            return 'decreasing'
    except (ValueError, TypeError):
        return 'stable'

def get_previous_reading(conn, name, data_type):
    """Get the most recent reading for trend calculation"""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT inflow_discharge, outflow_discharge 
            FROM telemetry_history 
            WHERE name = ? AND type = ? 
            ORDER BY fetched_at DESC 
            LIMIT 1
        ''', (name, data_type))
        
        result = cursor.fetchone()
        return result if result else (None, None)
    except Exception:
        return None, None

def store_telemetry_data(dams_data, headworks_data):
    """Store fetched data in the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        timestamp = datetime.now().isoformat()
        stored_count = 0
        
        # Store dams data
        for dam in dams_data.get('dams', []):
            try:
                name = dam.get('name', 'Unknown')
                inflow = dam.get('inflow_discharge')
                outflow = dam.get('outflow_discharge')
                
                # Get previous readings for trend calculation
                prev_inflow, prev_outflow = get_previous_reading(conn, name, 'dam')
                
                # Calculate trends
                inflow_trend = calculate_trend(inflow, prev_inflow)
                outflow_trend = calculate_trend(outflow, prev_outflow)
                
                # Insert new record
                conn.execute('''
                    INSERT OR REPLACE INTO telemetry_history 
                    (name, type, inflow_discharge, outflow_discharge, inflow_trend, outflow_trend, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, 'dam', inflow, outflow, inflow_trend, outflow_trend, timestamp))
                
                stored_count += 1
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to store dam {dam.get('name', 'Unknown')}: {str(e)}")
        
        # Store headworks data
        for headwork in headworks_data.get('headworks', []):
            try:
                name = headwork.get('name', 'Unknown')
                inflow = headwork.get('inflow_discharge')
                outflow = headwork.get('outflow_discharge')
                
                # Get previous readings for trend calculation
                prev_inflow, prev_outflow = get_previous_reading(conn, name, 'headwork')
                
                # Calculate trends
                inflow_trend = calculate_trend(inflow, prev_inflow)
                outflow_trend = calculate_trend(outflow, prev_outflow)
                
                # Insert new record
                conn.execute('''
                    INSERT OR REPLACE INTO telemetry_history 
                    (name, type, inflow_discharge, outflow_discharge, inflow_trend, outflow_trend, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, 'headwork', inflow, outflow, inflow_trend, outflow_trend, timestamp))
                
                stored_count += 1
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to store headwork {headwork.get('name', 'Unknown')}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Stored {stored_count} records in database")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database storage failed: {str(e)}")
        return False

def collect_and_store_data():
    """Main function to collect and store data"""
    logger.info("=" * 60)
    logger.info(f"🔄 Starting scheduled data collection at {datetime.now()}")
    
    # Fetch data from FFD APIs
    dams_data, headworks_data = fetch_ffd_data()
    
    if dams_data and headworks_data:
        # Store in database
        if store_telemetry_data(dams_data, headworks_data):
            logger.info("✅ Data collection completed successfully!")
        else:
            logger.error("❌ Data collection failed during storage")
    else:
        logger.error("❌ Data collection failed during API fetch")
    
    logger.info("=" * 60)

def run_scheduler():
    """Run the scheduler"""
    logger.info("🚀 Hydrological Data Collector Starting...")
    logger.info(f"📁 Database: {DB_PATH}")
    logger.info(f"📝 Log file: {LOG_PATH}")
    
    # Initialize database
    if not init_database():
        logger.error("❌ Failed to initialize database. Exiting.")
        return
    
    # Schedule data collection every 6 hours
    schedule.every(6).hours.do(collect_and_store_data)
    
    logger.info("⏰ Scheduled data collection every 6 hours")
    logger.info("📊 Collection times: 00:00, 06:00, 12:00, 18:00")
    
    # Run initial collection
    logger.info("🔄 Running initial data collection...")
    collect_and_store_data()
    
    # Keep the scheduler running
    logger.info("🔄 Scheduler running... Press Ctrl+C to stop")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("⏹️ Scheduler stopped by user")

if __name__ == "__main__":
    run_scheduler()
