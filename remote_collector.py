#!/usr/bin/env python3
"""Remote collector script with database support.
Data source: pm-dashboard POST endpoint (requires API key) -> derive dams & headworks.
Failure behaviour: if attempts fail (DNS / network / auth), raise and exit non-zero so CI fails.

NEW: Also updates SQLite database directly (same structure as Flask app)

Environment variables:
    FFD_API_KEY  (required) API key for endpoint https://ffd.pmd.gov.pk/api/pm-dashboard
    MAX_ATTEMPTS (optional) retry attempts for dashboard fetch (default 1)
  DB_PATH      (optional) path to SQLite database (default: hydro_history.db)
"""

import json, sys, requests, datetime, time, os, socket, sqlite3
from threading import Lock

PM_DASHBOARD = 'https://ffd.pmd.gov.pk/api/pm-dashboard'

OUT_FILE = 'latest.json'
API_KEY = os.environ.get('FFD_API_KEY', '').strip()
MAX_ATTEMPTS = max(1, int(os.environ.get('MAX_ATTEMPTS', '1')))
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

def swap_lat_long(items):
    """Swap lat and long values in a list of items.
    FFD API has lat/long swapped - this corrects them for proper display.
    """
    if not items:
        return items

    for item in items:
        if 'lat' in item and 'long' in item:
            # Swap the values
            item['lat'], item['long'] = item['long'], item['lat']

    return items

def store_to_database(dams_data, headworks_data):
    if not dams_data.get('dams') and not headworks_data.get('headworks'):
        print('[DB] No data to store to database')
        return
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        fetched_at = datetime.datetime.utcnow().isoformat()

        def has_changed(row):
            """Check if current telemetry differs from the latest DB record"""
            cur.execute("""
                SELECT inflow_discharge, outflow_discharge, reservoir_level, storage,
                       status, inflow_trend, outflow_trend, recorded_at
                FROM telemetry_history
                WHERE name=? AND type=?
                ORDER BY id DESC LIMIT 1
            """, (row[0], row[1]))
            prev = cur.fetchone()
            return prev != row[2:-1]  # compare values (skip fetched_at)

        all_rows = []

        # dams
        for dam in dams_data.get('dams', []):
            row = (
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
            )
            if has_changed(row):
                all_rows.append(row)

        # headworks
        for headwork in headworks_data.get('headworks', []):
            row = (
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
            )
            if has_changed(row):
                all_rows.append(row)

        try:
            if all_rows:
                cur.executemany("""
                    INSERT INTO telemetry_history (
                        name, type, inflow_discharge, outflow_discharge, reservoir_level, storage,
                        status, inflow_trend, outflow_trend, recorded_at, fetched_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, all_rows)
                conn.commit()
                print(f'[DB] Stored {len(all_rows)} new records')
            else:
                print('[DB] No changes detected, skipping insert.')
        except Exception:
            conn.rollback()
            raise
        finally:
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
            http_hint = ''
            response = getattr(e, 'response', None)
            if response is not None:
                body_preview = (response.text or '').replace('\n', ' ').strip()[:180]
                http_hint = f' [HTTP {response.status_code}]'
                if body_preview:
                    http_hint += f' body="{body_preview}"'

            if attempt < MAX_ATTEMPTS:
                wait = attempt * 2
                print(f'[WARN] Attempt {attempt}/{MAX_ATTEMPTS} failed for {url}: {e}{dns_hint}{http_hint}. Retrying in {wait}s...')
                time.sleep(wait)
            else:
                print(f'[WARN] Attempt {attempt}/{MAX_ATTEMPTS} failed for {url}: {e}{dns_hint}{http_hint}. No more retries.')
    raise RuntimeError(f'All {MAX_ATTEMPTS} attempts failed for {url}: {last_error}')

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
        raise RuntimeError('FFD_API_KEY not provided for dashboard method')
    print(f'[INFO] Using pm-dashboard API key (len={len(API_KEY)})')
    data = retry_fetch_json('POST', PM_DASHBOARD, data={'API_KEY': API_KEY})
    if 'data' not in data or not isinstance(data['data'], list):
        raise RuntimeError('Unexpected pm-dashboard structure')
    if not data['data']:
        # No telemetry items returned -> treat as failure so run doesn't update outputs
        raise RuntimeError('pm-dashboard returned no data')
    dams, headworks = categorize_from_telemetries(data['data'])
    return {'dams': dams['dams']}, {'headworks': headworks['headworks']}

def write_payload_and_db(dams, headworks):
    """Write both JSON file and database"""
    # Swap lat/long for correct display (FFD API has them reversed)
    swap_lat_long(dams.get('dams', []))
    swap_lat_long(headworks.get('headworks', []))
    # Prepare payload but don't write it yet. Ensure DB write succeeds first.
    payload = {
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'dams': dams,
        'headworks': headworks
    }

    # Store to database first; any DB error should abort the run and prevent JSON update.
    store_to_database(dams, headworks)

    # If DB storage succeeded, write JSON atomically to avoid partial updates.
    tmp_file = OUT_FILE + '.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp_file, OUT_FILE)
    print(f'[JSON] Wrote {OUT_FILE}: dams={len(dams.get("dams", []))} headworks={len(headworks.get("headworks", []))}')

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
    # Fail fast: DB must be initialized for safe runs.
    init_db()

    print('[INFO] Collecting from pm-dashboard endpoint...', flush=True)
    dams, headworks = fetch_via_dashboard()
    write_payload_and_db(dams, headworks)
    print('[DONE] Collected via pm-dashboard (JSON + DB updated).', flush=True)
    return 0

if __name__ == '__main__':
    # Exit with the code returned by main() so failures propagate to CI/workflow.
    code = main()
    sys.exit(code)
