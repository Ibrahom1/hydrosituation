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

# FFD API Configuration
FFD_TOKEN = "PM_PORT_API_1a2b9c6d5e4f"
FFD_API_URL = "https://ffd.pmd.gov.pk/api/pm-dashboard"

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

# ---- Historical Data Storage (SQLite) ----
DB_PATH = 'hydro_history.db'
# Optional remote JSON dataset URL (produced by remote collector running every 6h)
# You can override via environment variable REMOTE_DATA_URL
REMOTE_DATA_URL = os.environ.get('REMOTE_DATA_URL', '').strip()  # e.g. https://raw.githubusercontent.com/youruser/hydro-dataset/main/latest.json
DB_LOCK = Lock()
LAST_CACHE = {'data': None, 'fetched_at': None}

def init_db():
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
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

def parse_number(value):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).replace(',', '').strip()
        return float(value) if value else None
    except Exception:
        return None

def store_history(items, item_type):
    if not items:
        return
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        fetched_at = datetime.utcnow().isoformat()
        rows = []
        for item in items:
            rows.append((
                item.get('name','').strip(),
                item_type,
                parse_number(item.get('inflow_discharge')),
                parse_number(item.get('outflow_discharge')),
                parse_number(item.get('reservoir_level')),
                parse_number(item.get('storage')),
                item.get('status'),
                item.get('inflow_trend'),
                item.get('outflow_trend'),
                item.get('recording_time'),
                fetched_at
            ))
        cur.executemany("""
            INSERT OR IGNORE INTO telemetry_history (
                name, type, inflow_discharge, outflow_discharge, reservoir_level, storage, status,
                inflow_trend, outflow_trend, recorded_at, fetched_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()
        conn.close()

def fetch_history(name, hours=24):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT inflow_discharge, outflow_discharge, fetched_at
            FROM telemetry_history
            WHERE UPPER(name)=? AND fetched_at >= ?
            ORDER BY fetched_at ASC
        """, (name.upper().strip(), cutoff.isoformat()))
        rows = cur.fetchall()
        conn.close()
    inflow_series = []
    outflow_series = []
    for inflow, outflow, ts in rows:
        if inflow is not None:
            inflow_series.append({'x': ts, 'y': inflow})
        if outflow is not None:
            outflow_series.append({'x': ts, 'y': outflow})
    return inflow_series, outflow_series

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

def cache_and_store(dams, headworks, telemetries):
    store_history(dams, 'DAM')
    store_history(headworks, 'HEADWORK')
    LAST_CACHE['data'] = {
        'dams': dams,
        'headworks': headworks,
        'all_telemetries': telemetries,
        'timestamp': datetime.utcnow().isoformat(),
        'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }
    LAST_CACHE['fetched_at'] = datetime.utcnow()

def needs_refresh(max_age_minutes=10):
    if LAST_CACHE['fetched_at'] is None:
        return True
    return (datetime.utcnow() - LAST_CACHE['fetched_at']) > timedelta(minutes=max_age_minutes)

def fetch_remote_telemetries():
    logging.info("Fetching FFD telemetries (remote call)...")
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
    cache_and_store(dams, headworks, telemetries)
    return LAST_CACHE['data']
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
    cache_and_store(dams, headworks, telemetries)
    return LAST_CACHE['data']

def get_cached_or_fetch():
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

@app.route('/')
def index():
    return "Hydrological Situation Dashboard API - FFD Telemetries Only"

@app.route('/api/collect-data')
def collect_data():
    """Endpoint for cron-job.org to trigger data collection every 6 hours"""
    try:
        print(f"🚀 Data collection triggered at {datetime.now()}")
        
        # Fetch from FFD APIs
        print("📡 Fetching dams data...")
        dams_response = requests.get('https://ffd.gov.pk/api/dams', timeout=60)
        
        print("📡 Fetching headworks data...")
        headworks_response = requests.get('https://ffd.gov.pk/api/headworks', timeout=60)
        
        if dams_response.ok and headworks_response.ok:
            dams_data = dams_response.json()
            headworks_data = headworks_response.json()
            
            # Store to local database
            with DB_LOCK:
                conn = sqlite3.connect(DB_PATH)
                store_telemetry_data(conn, dams_data, headworks_data)
                conn.close()
            
            dam_count = len(dams_data.get('dams', []))
            headwork_count = len(headworks_data.get('headworks', []))
            
            print(f"✅ Data collected and stored successfully")
            print(f"   - Dams: {dam_count} items")
            print(f"   - Headworks: {headwork_count} items")
            
            return jsonify({
                "success": True,
                "message": "Data collected and stored successfully",
                "timestamp": datetime.now().isoformat(),
                "dams_count": dam_count,
                "headworks_count": headwork_count
            })
            
        else:
            error_msg = f"API Error: Dams {dams_response.status_code}, Headworks {headworks_response.status_code}"
            print(f"❌ {error_msg}")
            return jsonify({
                "success": False, 
                "error": error_msg
            }), 500
            
    except Exception as e:
        error_msg = f"Collection failed: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({
            "success": False, 
            "error": error_msg
        }), 500

def store_telemetry_data(conn, dams_data, headworks_data):
    """Store telemetry data from cloud sync"""
    timestamp = datetime.now().isoformat()
    
    # Store dams data
    for dam in dams_data.get('dams', []):
        conn.execute('''
            INSERT OR REPLACE INTO telemetry_history 
            (name, type, inflow_discharge, outflow_discharge, inflow_trend, outflow_trend, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            dam.get('name', ''),
            'dam',
            dam.get('inflow_discharge', 0),
            dam.get('outflow_discharge', 0),
            dam.get('inflow_trend', ''),
            dam.get('outflow_trend', ''),
            timestamp
        ))
    
    # Store headworks data
    for headwork in headworks_data.get('headworks', []):
        conn.execute('''
            INSERT OR REPLACE INTO telemetry_history 
            (name, type, inflow_discharge, outflow_discharge, inflow_trend, outflow_trend, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            headwork.get('name', ''),
            'headwork',
            headwork.get('inflow_discharge', 0),
            headwork.get('outflow_discharge', 0),
            headwork.get('inflow_trend', ''),
            headwork.get('outflow_trend', ''),
            timestamp
        ))
    
    conn.commit()

def apply_remote_dataset(payload):
    """Apply a remote dataset JSON structure to local DB/history cache.
    Expected structure: {
        "timestamp": str,
        "dams": {"dams": [...]},
        "headworks": {"headworks": [...]}  (either raw arrays or wrapped)
    }
    """
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

        with DB_LOCK:
            conn = sqlite3.connect(DB_PATH)
            store_telemetry_data(conn, {'dams': dams_items}, {'headworks': headworks_items})
            conn.close()
        # Update in-memory cache if newer
        cache_and_store(dams_items, headworks_items, dams_items + headworks_items)
        return True, f"Applied remote dataset with {len(dams_items)} dams & {len(headworks_items)} headworks"
    except Exception as e:
        return False, str(e)

@app.route('/api/sync-remote')
def sync_remote():
    """Fetch remote JSON dataset (produced by external cron collector) and store locally.
    Query param 'url' overrides configured REMOTE_DATA_URL for manual testing.
    """
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
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'FFD Hydrological Dashboard'
    })

@app.route('/api/ffd-telemetries')
def get_ffd_telemetries():
    """Return current telemetries (cached) and record new history if refreshed."""
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
            'all_telemetries': data['all_telemetries']
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
            'dams': data['dams']
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
            'river_summary': {river: len(hw) for river, hw in river_groups.items()}
        })
    except Exception as e:
        logging.error(f"Error getting headwork data: {e}")
        return jsonify({'success': False, 'error': str(e), 'timestamp': datetime.utcnow().isoformat()}), 500

@app.route('/api/history')
def get_history():
    name = request.args.get('name')
    hours = int(request.args.get('hours', 24))
    if not name:
        return jsonify({'success': False, 'error': 'Missing name parameter'}), 400
    inflow_series, outflow_series = fetch_history(name, hours)
    return jsonify({
        'success': True,
        'name': name,
        'hours': hours,
        'inflow': inflow_series,
        'outflow': outflow_series,
        'points': max(len(inflow_series), len(outflow_series))
    })

# ---- Scheduler (4x per day, every 6 hours) ----
def scheduled_job():
    try:
        logging.info('Scheduled fetch start')
        fetch_remote_telemetries()
        logging.info('Scheduled fetch complete')
    except Exception as e:
        logging.error(f'Scheduled fetch failed: {e}')

def start_scheduler():
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scheduled_job, 'interval', hours=6, next_run_time=datetime.utcnow())
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
    logging.info('Scheduler started (6h interval)')

if __name__ == '__main__':
    print("Starting Hydrological Situation Dashboard API...")
    init_db()
    start_scheduler()
    print("FFD Telemetries Service Only + History + Scheduler")
    print("Available endpoints:")
    print("  - /api/health")
    print("  - /api/ffd-telemetries")
    print("  - /api/ffd-dams")
    print("  - /api/ffd-headworks")
    print("  - /api/history?name=Kalabagh&hours=24")
    
    # Get port from environment or use 5000 locally
    import os
    port = int(os.environ.get('PORT', 5000))
    
    # Disable the reloader explicitly to avoid ImportError with older watchdog versions.
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=port)
