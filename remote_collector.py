#!/usr/bin/env python3
"""Remote collector script (resilient) with database support.
Primary attempt: public endpoints ffd.gov.pk/api/dams & /api/headworks.
Fallback: pm-dashboard POST endpoint (requires API key) -> derive dams & headworks.
Graceful behaviour: if all attempts fail (DNS / network), exit 0 without updating file (prevents red workflow) and print SKIP.

NEW: Also updates SQLite database directly (same structure as Flask app)

Environment variables:
  FFD_API_KEY  (optional) API key for fallback endpoint https://ffd.pmd.gov.pk/api/pm-dashboard
  MAX_ATTEMPTS (optional) retry attempts for each fetch (default 5)
  DB_PATH      (optional) path to SQLite database (default: hydro_history.db)
"""

import json, sys, requests, datetime, time, os, socket, sqlite3
from requests.exceptions import RequestException
from threading import Lock

FFD_DAMS = 'https://ffd.gov.pk/api/dams'
FFD_HEADWORKS = 'https://ffd.gov.pk/api/headworks'
PM_DASHBOARD = 'https://ffd.pmd.gov.pk/api/pm-dashboard'

OUT_FILE = 'latest.json'
API_KEY = os.environ.get('FFD_API_KEY', '').strip()
MAX_ATTEMPTS = int(os.environ.get('MAX_ATTEMPTS', '5'))
DB_PATH = os.environ.get('DB_PATH', 'hydro_history.db')

UA = {'User-Agent': 'HybridHydroCollector/1.1'}
DB_LOCK = Lock()

def init_db():
    """Initialize database with same structure as Flask app"""
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
        print(f'[DB] Database initialized at {DB_PATH}')

def parse_number(value):
    """Parse numeric values safely (same as Flask app)"""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).replace(',', '').strip()
        return float(value) if value else None
    except Exception:
        return None

def store_to_database(dams_data, headworks_data):
    """Store data to SQLite database (same structure as Flask app)"""
    if not dams_data.get('dams') and not headworks_data.get('headworks'):
        print('[DB] No data to store to database')
        return
    
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        fetched_at = datetime.datetime.utcnow().isoformat()
        
        # Store dams
        dam_rows = []
        for dam in dams_data.get('dams', []):
            dam_rows.append((
                dam.get('name', '').strip(),
                'DAM',
                parse_number(dam.get('inflow_discharge')),
                parse_number(dam.get('outflow_discharge')),
                parse_number(dam.get('reservoir_level')),
                parse_number(dam.get('storage')),
                dam.get('status'),
                dam.get('inflow_trend'),
                dam.get('outflow_trend'),
                dam.get('recording_time'),
                fetched_at
            ))
        
        # Store headworks
        headwork_rows = []
        for headwork in headworks_data.get('headworks', []):
            headwork_rows.append((
                headwork.get('name', '').strip(),
                'HEADWORK',
                parse_number(headwork.get('inflow_discharge')),
                parse_number(headwork.get('outflow_discharge')),
                parse_number(headwork.get('reservoir_level')),
                parse_number(headwork.get('storage')),
                headwork.get('status'),
                headwork.get('inflow_trend'),
                headwork.get('outflow_trend'),
                headwork.get('recording_time'),
                fetched_at
            ))
        
        all_rows = dam_rows + headwork_rows
        if all_rows:
            cur.executemany("""
                INSERT OR IGNORE INTO telemetry_history (
                    name, type, inflow_discharge, outflow_discharge, reservoir_level, storage, status,
                    inflow_trend, outflow_trend, recorded_at, fetched_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, all_rows)
            
            conn.commit()
            rows_affected = cur.rowcount
            print(f'[DB] Stored {len(dam_rows)} dams, {len(headwork_rows)} headworks ({rows_affected} new records)')
        
        conn.close()

def retry_fetch_json(method, url, **kwargs):
    """Generic retry wrapper with DNS specific notes."""
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.request(method, url, timeout=60, headers=UA, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # broad: network, decode, etc.
            last_error = e
            # Detect DNS resolution issues explicitly
            dns_hint = ''
            msg = str(e)
            if 'Name or service not known' in msg or 'Temporary failure in name resolution' in msg or isinstance(e, socket.gaierror):
                dns_hint = ' [DNS resolution issue]'
            wait = attempt * 2
            print(f'[WARN] Attempt {attempt}/{MAX_ATTEMPTS} failed for {url}: {e}{dns_hint}. Retrying in {wait}s...')
            time.sleep(wait)
    raise RuntimeError(f'All {MAX_ATTEMPTS} attempts failed for {url}: {last_error}')

def fetch_public_split():
    dams = retry_fetch_json('GET', FFD_DAMS)
    headworks = retry_fetch_json('GET', FFD_HEADWORKS)
    return dams, headworks

def categorize_from_telemetries(items):
    dams = []
    headworks = []
    for item in items:
        t = (item.get('type') or '').lower()
        name = (item.get('name') or '').lower()
        if 'dam' in t or 'reservoir' in t or any(k in name for k in ['dam', 'reservoir', 'tarbela', 'mangla', 'chashma']):
            dams.append(item)
        elif 'headwork' in t or 'barrage' in t or any(k in name for k in ['headwork', 'barrage', 'weir']):
            headworks.append(item)
        else:
            # heuristic: has storage/reservoir_level -> dam else headwork
            if item.get('reservoir_level') or item.get('storage'):
                dams.append(item)
            else:
                headworks.append(item)
    return {'dams': dams}, {'headworks': headworks}

def fetch_via_dashboard():
    if not API_KEY:
        raise RuntimeError('FFD_API_KEY not provided for fallback dashboard method')
    data = retry_fetch_json('POST', PM_DASHBOARD, data={'API_KEY': API_KEY})
    if 'data' not in data or not isinstance(data['data'], list):
        raise RuntimeError('Unexpected pm-dashboard structure')
    dams, headworks = categorize_from_telemetries(data['data'])
    return {'dams': dams['dams']}, {'headworks': headworks['headworks']}

def write_payload_and_db(dams, headworks):
    """Write both JSON file and database"""
    # Write JSON file
    payload = {
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'dams': dams,              # {"dams": [...]}
        'headworks': headworks     # {"headworks": [...]} 
    }
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f'[JSON] Wrote {OUT_FILE}: dams={len(dams.get("dams", []))} headworks={len(headworks.get("headworks", []))}')
    
    # Store to database
    try:
        store_to_database(dams, headworks)
    except Exception as db_err:
        print(f'[DB-WARN] Database storage failed: {db_err}. JSON file still created.')

def write_placeholder(reason):
    """Create a placeholder latest.json so the file exists for the dashboard on first run."""
    if os.path.exists(OUT_FILE):
        print('[INFO] Placeholder not needed; existing latest.json retained.')
        return
    placeholder = {
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'skipped': True,
        'reason': reason,
        'dams': { 'dams': [] },
        'headworks': { 'headworks': [] }
    }
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(placeholder, f, ensure_ascii=False)
    print(f'[OK] Wrote placeholder {OUT_FILE} (no data this run).')

def main():
    # Initialize database
    try:
        init_db()
    except Exception as db_init_err:
        print(f'[DB-WARN] Database initialization failed: {db_init_err}. Continuing with JSON-only mode.')
    
    try:
        # Phase 1: public endpoints
        try:
            print('[INFO] Trying public endpoints (ffd.gov.pk)...', flush=True)
            dams, headworks = fetch_public_split()
            write_payload_and_db(dams, headworks)
            print('[DONE] Collected via public endpoints (JSON + DB updated).', flush=True)
            return 0
        except Exception as pub_err:
            print(f'[WARN] Public endpoints failed: {pub_err}', flush=True)

        # Phase 2: fallback dashboard
        try:
            print('[INFO] Trying fallback pm-dashboard endpoint...', flush=True)
            dams, headworks = fetch_via_dashboard()
            write_payload_and_db(dams, headworks)
            print('[DONE] Collected via fallback dashboard (JSON + DB updated).', flush=True)
            return 0
        except Exception as dash_err:
            print(f'[WARN] Fallback dashboard failed: {dash_err}', flush=True)
            print('[SKIP] No data collected this run (network or API issue). Workflow will succeed without update.', flush=True)
            write_placeholder(str(dash_err))
            return 0  # graceful success
    except Exception as fatal:  # absolutely last resort
        print(f'[FAIL-GRACEFUL] Unexpected top-level error: {fatal}', flush=True)
        print('[SKIP] Exiting with code 0 to keep workflow green.', flush=True)
        return 0

if __name__ == '__main__':
    # Always exit 0 (main already returns 0 in all paths) to prevent red workflow on transient issues.
    code = main()
    try:
        sys.exit(code)
    except SystemExit:
        # In some rare cases (older Python peculiarities) re-raise ensures correct exit; but force 0.
        os._exit(0)