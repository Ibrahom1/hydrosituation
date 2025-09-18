from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import logging
from datetime import datetime, timedelta
import sqlite3
import os
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# Configure CORS to allow all origins for development
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# FFD API Configuration (token loaded from environment or .env)
from dotenv import load_dotenv
load_dotenv()
FFD_TOKEN = os.environ.get('FFD_API_KEY', '').strip()
FFD_API_URL = "https://ffd.pmd.gov.pk/api/pm-dashboard"
if not FFD_TOKEN:
    logging.warning("FFD_API_KEY not set in environment; remote fetch endpoints will fail until provided.")

"""River configuration and variants.
We include common spelling variants to improve matching and classification.
"""
RIVER_HEADWORKS_MAP = {
    "INDUS": [
        "TARBELA", "ATTOCK", "KALABAGH", "CHASHMA", "TAUNSA", "GUDDU", "SUKKUR", "KOTRI"
    ],
    "JHELUM": [
        "KOHALA", "MANGLA", "RASUL"
    ],
    "CHENAB": [
        "JAMMU TAWI", "JAMMU", "AKHNUR", "MARALA", "KHANKI", "QADIRABAD", "Q.ABAD", "QADIR ABAD", "CHINIOT BRIDGE", "CHINIOT", "TRIMMU", "PANJNAD", "PANJNAD HEADWORKS", "PARTAB BRIDGE (BUNJI)"
    ],
    "RAVI": [
        "JASSAR", "RAVI SYPHON", "SHAHDARA", "BALLOKI", "SIDHNAI"
    ],
    "SUTLEJ": [
        "SULEMANKI", "SULEMAN KI", "ISLAM", "G.S. WALA", "G.S.WALA", "G.S WALA", "GS WALA", "GANDA SINGH WALA"
    ],
    "KABUL": [
        "WARSAK", "NOWSHERA", "KABUL"
    ]
}

# ---- Historical Data Storage (SQLite) - READ ONLY ----
# Resolve DB path relative to this file so it works no matter where app.py is launched from
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(APP_DIR, '..', 'hydro_history.db'))
# Optional remote JSON dataset URL (produced by remote collector running every 6h)
REMOTE_DATA_URL = os.environ.get('REMOTE_DATA_URL', '').strip()
DB_LOCK = Lock()
LAST_CACHE = {'data': None, 'fetched_at': None}

def init_db():
    """Initialize database structure if it doesn't exist (read-only app)"""
    if not os.path.exists(DB_PATH):
        logging.warning(f"Database not found at {DB_PATH}. Remote collector should create it.")
        return
    
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Only create table if it doesn't exist (non-destructive)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                inflow_discharge REAL,
                outflow_discharge REAL,
                reservoir_level REAL,
                storage REAL,
                status TEXT,
                inflow_trend TEXT,
                outflow_trend TEXT,
                recorded_at TEXT,
                fetched_at TEXT NOT NULL,
                UNIQUE(name, type, fetched_at)
            )
        """)
        conn.commit()
        conn.close()
        logging.info(f"Database verified at {DB_PATH}")

def parse_number(value):
    """Parse numeric values safely"""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).replace(',', '').strip()
        return float(value) if value else None
    except Exception:
        return None

def parse_recorded_at(recorded_at_str, fallback_year: int | None = None):
    """Parse recorded_at timestamp like '19-Aug 06 PST' to datetime.
    If year is missing, use fallback_year when provided, otherwise current year.
    """
    if not recorded_at_str:
        return None
    try:
        # Parse format like "19-Aug 06 PST" or "19-Aug 12 PST"
        parts = recorded_at_str.strip().split()
        if len(parts) >= 3:
            date_part = parts[0]  # "19-Aug"
            time_part = parts[1]  # "06" or "12"
            
            # Parse day and month
            day, month_str = date_part.split('-')
            day = int(day)
            
            # Convert month abbreviation to number
            month_map = {
                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
            }
            month = month_map.get(month_str, 1)
            
            # Parse hour (assume provided fallback year or current year)
            hour = int(time_part)
            year = fallback_year if fallback_year else datetime.utcnow().year
            
            return datetime(year, month, day, hour, 0, 0)
    except Exception as e:
        logging.warning(f"Could not parse recorded_at '{recorded_at_str}': {e}")
    return None

def fetch_history_extended(name, days=7):
    """Fetch history for multiple days using recorded_at, robust across years.
    Uses fetched_at to derive the proper year for recorded_at values.
    """
    if not os.path.exists(DB_PATH):
        logging.warning(f"Database not found at {DB_PATH}")
        return [], []

    with DB_LOCK:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT inflow_discharge, outflow_discharge, recorded_at, fetched_at
                FROM telemetry_history
                WHERE UPPER(name)=? AND recorded_at IS NOT NULL
                ORDER BY fetched_at ASC
                """,
                (name.upper().strip(),),
            )
            rows = cur.fetchall()
            conn.close()
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            return [], []

    if not rows:
        logging.warning(f"No history rows found for {name}")
        return [], []

    # Determine latest by fetched_at
    def parse_iso(dt_str):
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None

    fetched_times = [parse_iso(r[3]) for r in rows if r[3]]
    latest_fetch = max([ft for ft in fetched_times if ft], default=None)
    if not latest_fetch:
        logging.warning(f"No valid fetched_at timestamps for {name}")
        return [], []

    cutoff_datetime = latest_fetch - timedelta(days=days)
    logging.info(f"Debug: Latest fetched_at for {name}: {latest_fetch}")
    logging.info(f"Debug: Looking for data from {cutoff_datetime} onwards (last {days} days)")

    filtered_rows = []
    for inflow, outflow, recorded_at, fetched_at in rows:
        ft = parse_iso(fetched_at)
        fallback_year = ft.year if ft else None
        parsed_time = parse_recorded_at(recorded_at, fallback_year)
        if parsed_time and parsed_time >= cutoff_datetime:
            filtered_rows.append((inflow, outflow, recorded_at))

    logging.info(f"Debug: Found {len(filtered_rows)} rows within last {days} days for {name}")
    inflow_series, outflow_series = [], []
    for inflow, outflow, rec in filtered_rows:
        ts = rec if rec else "Unknown time"
        if inflow is not None:
            inflow_series.append({"x": ts, "y": inflow})
        if outflow is not None:
            outflow_series.append({"x": ts, "y": outflow})
    return inflow_series, outflow_series

def fetch_history_between(name, start_date, end_date):
    """Fetch history between two calendar dates (inclusive) by parsing recorded_at.
    Dates are strings 'YYYY-MM-DD'. Returns inflow and outflow series.
    """
    if not os.path.exists(DB_PATH):
        logging.warning(f"Database not found at {DB_PATH}")
        return [], []

    # Parse incoming dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    except Exception as e:
        logging.error(f"Invalid date range params: {start_date} - {end_date}: {e}")
        return [], []

    with DB_LOCK:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT inflow_discharge, outflow_discharge, recorded_at, fetched_at
                FROM telemetry_history
                WHERE UPPER(name)=? AND recorded_at IS NOT NULL
                ORDER BY fetched_at ASC
                """,
                (name.upper().strip(),),
            )
            rows = cur.fetchall()
            conn.close()
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            return [], []

    # Filter rows by parsed recorded_at
    inflow_series, outflow_series = [], []
    for inflow, outflow, recorded_at, fetched_at in rows:
        # Use fetched_at year as fallback for year-less recorded_at strings
        fallback_year = None
        try:
            fallback_year = datetime.fromisoformat(fetched_at).year if fetched_at else None
        except Exception:
            fallback_year = None
        pt = parse_recorded_at(recorded_at, fallback_year)
        if not pt:
            continue
        if start_dt <= pt <= end_dt:
            ts = recorded_at or "Unknown time"
            if inflow is not None:
                inflow_series.append({"x": ts, "y": inflow})
            if outflow is not None:
                outflow_series.append({"x": ts, "y": outflow})

    return inflow_series, outflow_series

def fetch_history(name, hours=24):
    """Legacy function - converts hours to days"""
    days = max(1, hours // 24)
    return fetch_history_extended(name, days)

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def categorize_headworks_by_river(headworks):
    """Categorize headworks by their respective rivers"""
    river_groups = {}
    
    # Initialize river groups
    for river in RIVER_HEADWORKS_MAP.keys():
        river_groups[river] = []
    
    # Add "OTHER" category for unmatched items
    river_groups["OTHER"] = []
    
    for headwork in headworks:
        headwork_name = headwork.get('name', '').upper().strip()
        assigned = False
        
        # Try to match with known river headworks
        for river, headwork_names in RIVER_HEADWORKS_MAP.items():
            for known_name in headwork_names:
                # More flexible matching
                if (known_name in headwork_name or 
                    headwork_name in known_name or
                    any(word in headwork_name for word in known_name.split()) or
                    any(word in known_name for word in headwork_name.split())):
                    river_groups[river].append(headwork)
                    assigned = True
                    break
            if assigned:
                break
        
        # If no match found, add to OTHER category
        if not assigned:
            river_groups["OTHER"].append(headwork)
    
    # Remove empty river groups
    river_groups = {river: headworks for river, headworks in river_groups.items() if headworks}
    
    return river_groups

def cache_only(dams, headworks, telemetries):
    """Cache data in memory only - NO database storage (remote collector handles DB)"""
    LAST_CACHE['data'] = {
        'dams': dams,
        'headworks': headworks,
        'all_telemetries': telemetries,
        'timestamp': datetime.utcnow().isoformat(),
        'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }
    LAST_CACHE['fetched_at'] = datetime.utcnow()
    logging.info(f"Cached {len(dams)} dams and {len(headworks)} headworks (no DB storage)")

def needs_refresh(max_age_minutes=10):
    """Check if cache needs refresh"""
    if LAST_CACHE['fetched_at'] is None:
        return True
    return (datetime.utcnow() - LAST_CACHE['fetched_at']) > timedelta(minutes=max_age_minutes)

def fetch_remote_telemetries():
    """Fetch fresh data from FFD API - CACHE ONLY, no database storage"""
    logging.info("Fetching FFD telemetries (remote call - cache only)...")
    request_data = {"API_KEY": FFD_TOKEN}
    try:
        response = requests.post(FFD_API_URL, data=request_data, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"FFD API request failed: {response.status_code}")
        data = response.json()
        if 'data' not in data or not isinstance(data['data'], list):
            raise RuntimeError('Invalid data structure from FFD API')
        telemetries = data['data']
        logging.info(f"Successfully fetched {len(telemetries)} telemetry records")
    except requests.exceptions.Timeout:
        logging.error("FFD API request timed out")
        raise RuntimeError("External API timeout - try again later")
    except requests.exceptions.RequestException as e:
        logging.error(f"FFD API request failed: {e}")
        raise RuntimeError(f"External API error: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error in fetch_remote_telemetries: {e}")
        raise RuntimeError(f"Data processing error: {str(e)}")
    
    # Classify data into dams and headworks
    dams = []
    headworks = []
    for item in telemetries:
        item_type = item.get('type', '').lower()
        name = item.get('name', '')
        if 'dam' in item_type or 'reservoir' in item_type or any(dam_keyword in name.lower() for dam_keyword in ['dam', 'reservoir', 'tarbela', 'mangla', 'chashma']):
            dams.append(item)
        elif 'headwork' in item_type or 'barrage' in item_type or any(hw_keyword in name.lower() for hw_keyword in ['headwork', 'barrage', 'weir']):
            headworks.append(item)
        else:
            if item.get('reservoir_level') or item.get('storage'):
                dams.append(item)
            else:
                headworks.append(item)
    
    # Only cache, don't store to database
    cache_only(dams, headworks, telemetries)
    return LAST_CACHE['data']

def get_cached_or_fetch():
    """Get data from cache or fetch fresh - NO database storage"""
    if needs_refresh():
        try:
            return fetch_remote_telemetries()
        except Exception as e:
            logging.error(f"Remote fetch failed: {e}")
            if LAST_CACHE['data']:
                logging.info("Serving stale cached data due to external API failure")
                return LAST_CACHE['data']
            else:
                # If no cache exists, create dummy data to prevent 500 errors
                logging.warning("No cache available, creating dummy data")
                dummy_data = {
                    'dams': [],
                    'headworks': [],
                    'all_telemetries': [],
                    'timestamp': datetime.utcnow().isoformat(),
                    'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                }
                LAST_CACHE['data'] = dummy_data
                LAST_CACHE['fetched_at'] = datetime.utcnow()
                return dummy_data
    return LAST_CACHE['data']

def apply_remote_dataset(payload):
    """Apply a remote dataset JSON structure to local cache only"""
    try:
        dams_block = payload.get('dams', {})
        headworks_block = payload.get('headworks', {})
        
        # Accept both wrapped ({"dams": [...]}) and direct list
        if isinstance(dams_block, dict):
            dams_items = dams_block.get('dams', [])
        else:
            dams_items = dams_block if isinstance(dams_block, list) else []
        if isinstance(headworks_block, dict):
            headworks_items = headworks_block.get('headworks', [])
        else:
            headworks_items = headworks_block if isinstance(headworks_block, list) else []

        # Only update cache, don't store to database
        cache_only(dams_items, headworks_items, dams_items + headworks_items)
        return True, f"Applied remote dataset to cache: {len(dams_items)} dams & {len(headworks_items)} headworks"
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    return "Hydrological Situation Dashboard API - Read-Only Mode (Remote Collector Updates DB)"

@app.route('/api/sync-remote')
def sync_remote():
    """Fetch remote JSON dataset and apply to cache only"""
    url = request.args.get('url') or REMOTE_DATA_URL
    if not url:
        return jsonify({'success': False, 'error': 'REMOTE_DATA_URL not configured'}), 400
    try:
        resp = requests.get(url, timeout=30, headers={'User-Agent': 'HydroDashboardSync/1.0'})
        if not resp.ok:
            return jsonify({'success': False, 'error': f'HTTP {resp.status_code} fetching remote dataset'}), 502
        payload = resp.json()
        ok, msg = apply_remote_dataset(payload)
        return jsonify({'success': ok, 'message': msg, 'source': url, 'timestamp': datetime.utcnow().isoformat()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    db_exists = os.path.exists(DB_PATH)
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'FFD Hydrological Dashboard (Read-Only)',
        'database_exists': db_exists,
        'database_path': DB_PATH,
        'mode': 'read_only'
    })

@app.route('/api/ffd-telemetries')
def get_ffd_telemetries():
    """Return current telemetries (cached only)"""
    try:
        data = get_cached_or_fetch()
        return jsonify({
            'success': True,
            'timestamp': data['timestamp'],
            'last_updated': data['last_updated'],
            'total_count': len(data['all_telemetries']),
            'dams_count': len(data['dams']),
            'headworks_count': len(data['headworks']),
            'dams': data['dams'],
            'headworks': data['headworks'],
            'all_telemetries': data['all_telemetries'],
            'source': 'cache_only'
        })
    except Exception as e:
        logging.error(f"Error getting telemetries: {e}")
        return jsonify({'success': False, 'error': str(e), 'timestamp': datetime.utcnow().isoformat()}), 500

@app.route('/api/ffd-dams')
def get_ffd_dams():
    """Get only dam data from FFD telemetries"""
    try:
        data = get_cached_or_fetch()
        return jsonify({
            'success': True,
            'timestamp': data['timestamp'],
            'last_updated': data['last_updated'],
            'count': len(data['dams']),
            'dams': data['dams'],
            'source': 'cache_only'
        })
    except Exception as e:
        logging.error(f"Error getting dam data: {e}")
        return jsonify({'success': False, 'error': str(e), 'timestamp': datetime.utcnow().isoformat()}), 500

@app.route('/api/ffd-headworks')
def get_ffd_headworks():
    """Get headwork data organized by rivers from FFD telemetries"""
    try:
        data = get_cached_or_fetch()
        headworks = data['headworks']
        river_groups = categorize_headworks_by_river(headworks)
        return jsonify({
            'success': True,
            'timestamp': data['timestamp'],
            'last_updated': data['last_updated'],
            'total_count': len(headworks),
            'rivers_count': len(river_groups),
            'headworks': headworks,
            'headworks_by_river': river_groups,
            'river_summary': {river: len(hw) for river, hw in river_groups.items()},
            'source': 'cache_only'
        })
    except Exception as e:
        logging.error(f"Error getting headwork data: {e}")
        return jsonify({'success': False, 'error': str(e), 'timestamp': datetime.utcnow().isoformat()}), 500

@app.route('/api/history')
def get_history():
    """Get historical data from database (read-only)"""
    name = request.args.get('name')
    days = int(request.args.get('days', 15))
    hours = int(request.args.get('hours', days * 24))
    start_date = request.args.get('start_date')  # YYYY-MM-DD
    end_date = request.args.get('end_date')      # YYYY-MM-DD
    
    if not name:
        return jsonify({'success': False, 'error': 'Missing name parameter'}), 400
    
    # If explicit date range provided, use it
    if start_date and end_date:
        inflow_series, outflow_series = fetch_history_between(name, start_date, end_date)
        return jsonify({
            'success': True,
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'inflow': inflow_series,
            'outflow': outflow_series,
            'points': max(len(inflow_series), len(outflow_series)),
            'source': 'database_readonly'
        })
    # Use days if provided, otherwise convert hours to days
    if request.args.get('days'):
        inflow_series, outflow_series = fetch_history_extended(name, days)
        return jsonify({
            'success': True,
            'name': name,
            'days': days,
            'inflow': inflow_series,
            'outflow': outflow_series,
            'points': max(len(inflow_series), len(outflow_series)),
            'source': 'database_readonly'
        })
    else:
        # Legacy hours-based request
        inflow_series, outflow_series = fetch_history(name, hours)
        return jsonify({
            'success': True,
            'name': name,
            'hours': hours,
            'inflow': inflow_series,
            'outflow': outflow_series,
            'points': max(len(inflow_series), len(outflow_series)),
            'source': 'database_readonly'
        })

@app.route('/api/storage-status')
def storage_status():
    """Check database storage status (read-only)"""
    if not os.path.exists(DB_PATH):
        return jsonify({
            'success': False,
            'error': f'Database not found at {DB_PATH}',
            'message': 'Remote collector should create and update the database'
        }), 404
    
    with DB_LOCK:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            
            # Get latest storage time
            cur.execute("SELECT MAX(fetched_at) FROM telemetry_history")
            last_stored = cur.fetchone()[0]
            
            # Get total record count
            cur.execute("SELECT COUNT(*) FROM telemetry_history")
            total_records = cur.fetchone()[0]
            
            # Get unique timestamps (should be every 6 hours)
            cur.execute("SELECT DISTINCT fetched_at FROM telemetry_history ORDER BY fetched_at DESC LIMIT 10")
            recent_timestamps = [row[0] for row in cur.fetchall()]
            
            # Get records per timestamp
            cur.execute("""
                SELECT fetched_at, COUNT(*) as record_count 
                FROM telemetry_history 
                GROUP BY fetched_at 
                ORDER BY fetched_at DESC 
                LIMIT 5
            """)
            timestamp_counts = [{'timestamp': row[0], 'count': row[1]} for row in cur.fetchall()]
            
            conn.close()
        except sqlite3.Error as e:
            return jsonify({'success': False, 'error': f'Database error: {e}'}), 500
    
    next_expected_time = None
    if last_stored:
        last_dt = datetime.fromisoformat(last_stored)
        next_expected_time = (last_dt + timedelta(hours=6)).isoformat()
    
    return jsonify({
        'success': True,
        'last_stored': last_stored,
        'next_expected': next_expected_time,
        'total_records': total_records,
        'recent_timestamps': recent_timestamps,
        'timestamp_counts': timestamp_counts,
        'hours_since_last': (datetime.utcnow() - datetime.fromisoformat(last_stored)).total_seconds() / 3600 if last_stored else None,
        'mode': 'read_only',
        'updater': 'remote_collector'
    })

# ---- NO SCHEDULER - Remote collector handles all updates ----
# Scheduler removed since remote collector handles all database updates

if __name__ == '__main__':
    print("Starting Hydrological Situation Dashboard API...")
    print("=== READ-ONLY MODE ===")
    print("Database updates handled by remote collector")
    
    # Verify database path
    print(f"Database path: {DB_PATH}")
    print(f"Absolute database path: {os.path.abspath(DB_PATH)}")
    print(f"Database exists: {os.path.exists(DB_PATH)}")
    
    init_db()
    
    print("FFD Telemetries Service (Read-Only Mode)")
    print("Available endpoints:")
    print("  - /api/health")
    print("  - /api/ffd-telemetries")
    print("  - /api/ffd-dams") 
    print("  - /api/ffd-headworks")
    print("  - /api/history?name=Kalabagh&days=7")
    print("  - /api/storage-status")
    print("  - /api/sync-remote")
    print("")
    print("Database updates: Remote collector only")
    print("Cache refresh: Every 10 minutes")
    
    # Get port from environment or use 5000 locally
    port = int(os.environ.get('PORT', 5000))
    
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=port)