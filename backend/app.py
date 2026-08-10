from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import logging
from datetime import datetime, timedelta
import sqlite3
import os
import glob
import re
from threading import Lock
# Scheduler not used in read-only mode
import csv
from functools import lru_cache
from typing import Optional, Dict, List

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
DAILY_WATER_DB_PATH = os.path.abspath(os.path.join(APP_DIR, '..', '..', 'data', 'daily_water_situation.sqlite'))
# Historical CSV path (June 15 to Aug 18, 2025)
CSV_PATH = os.path.abspath(os.path.join(APP_DIR, '..', 'historic2025flooddata_16june.csv'))
# Historical river CSVs (2014 to 2024)
COMBINED_CSV_PATTERN = os.path.abspath(os.path.join(APP_DIR, '..', 'combined_river_data_*.csv'))
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

def parse_recorded_at(recorded_at_str, fallback_year: Optional[int] = None):
    """Parse recorded_at timestamp like '19-Aug 06 PST' or '19-Aug-2025 06:00 PST' to datetime.
    If year is missing, use fallback_year when provided, otherwise current year.
    """
    if not recorded_at_str:
        return None
    try:
        parts = recorded_at_str.strip().split()
        if len(parts) >= 2:
            date_part = parts[0]  # "19-Aug" or "19-Aug-2025"
            time_part = parts[1]  # "06" or "06:00"
            
            date_bits = date_part.split('-')
            if len(date_bits) >= 2:
                day = int(date_bits[0])
                month_str = date_bits[1]
                explicit_year = int(date_bits[2]) if len(date_bits) >= 3 else None
                
                month_map = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }
                month = month_map.get(month_str.title()[:3], 1)
                
                if ':' in time_part:
                    hour_str, min_str = time_part.split(':', 1)
                    hour = int(hour_str)
                    minute = int(min_str)
                else:
                    hour = int(time_part)
                    minute = 0
                
                year = explicit_year if explicit_year else (fallback_year if fallback_year else datetime.utcnow().year)
                return datetime(year, month, day, hour, minute, 0)
    except Exception as e:
        logging.warning(f"Could not parse recorded_at '{recorded_at_str}': {e}")
    return None

def db_sites_for_ffd_name(requested_name: str) -> List[str]:
    """Resolve requested FFD site name to actual candidate site names stored in hydro_history.db."""
    if not requested_name:
        return []
    req_norm = normalize_name(requested_name)
    req_upper = requested_name.upper().strip()
    candidates = set()

    with DB_LOCK:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT name FROM telemetry_history")
            all_db_names = [r[0] for r in cur.fetchall()]
            conn.close()
        except sqlite3.Error:
            return [requested_name]

    for db_name in all_db_names:
        db_upper = db_name.upper().strip()
        db_norm = normalize_name(db_name)
        if db_upper == req_upper or db_norm == req_norm:
            candidates.add(db_name)
        elif db_norm.replace(' DAM', '') == req_norm.replace(' DAM', ''):
            candidates.add(db_name)
        elif db_upper.startswith(req_upper) or req_upper.startswith(db_upper):
            candidates.add(db_name)

    if req_upper in FFD_TO_CSV_NAME_MAP:
        for alias in FFD_TO_CSV_NAME_MAP[req_upper]:
            alias_norm = normalize_name(alias)
            for db_name in all_db_names:
                if normalize_name(db_name) == alias_norm:
                    candidates.add(db_name)

    if not candidates:
        candidates.add(requested_name)

    return list(candidates)

def format_db_timestamp(recorded_at_str: str, pt: datetime) -> str:
    """Format DB timestamp into standardized 'DD-Mon-YYYY HH:MM TZ' string with explicit year matching CSV format."""
    if not pt:
        return recorded_at_str or "Unknown time"
    month_map = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    tz_part = "PKT"
    if recorded_at_str:
        parts = recorded_at_str.strip().split()
        if len(parts) >= 3 and parts[-1].upper() in ('PST', 'PKT', 'UTC', 'EST', 'GMT'):
            tz_part = parts[-1].upper()
    return f"{pt.day:02d}-{month_map[pt.month-1]}-{pt.year} {pt.hour:02d}:{pt.minute:02d} {tz_part}"

def fetch_history_extended(name, days=7):
    """Fetch history for multiple days using recorded_at, robust across years.
    Uses fetched_at to derive the proper year for recorded_at values.
    """
    if not os.path.exists(DB_PATH):
        logging.warning(f"Database not found at {DB_PATH}")
        return [], []

    db_candidates = db_sites_for_ffd_name(name)
    placeholders = ','.join(['?'] * len(db_candidates))
    upper_candidates = [c.upper().strip() for c in db_candidates]

    with DB_LOCK:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT inflow_discharge, outflow_discharge, recorded_at, fetched_at
                FROM telemetry_history
                WHERE UPPER(name) IN ({placeholders}) AND recorded_at IS NOT NULL
                ORDER BY fetched_at ASC
                """,
                upper_candidates,
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
            ts = format_db_timestamp(recorded_at, parsed_time)
            filtered_rows.append((inflow, outflow, ts))

    logging.info(f"Debug: Found {len(filtered_rows)} rows within last {days} days for {name}")
    inflow_series, outflow_series = [], []
    for inflow, outflow, ts in filtered_rows:
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

    db_candidates = db_sites_for_ffd_name(name)
    placeholders = ','.join(['?'] * len(db_candidates))
    upper_candidates = [c.upper().strip() for c in db_candidates]

    with DB_LOCK:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT inflow_discharge, outflow_discharge, recorded_at, fetched_at
                FROM telemetry_history
                WHERE UPPER(name) IN ({placeholders}) AND recorded_at IS NOT NULL
                ORDER BY fetched_at ASC
                """,
                upper_candidates,
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
            ts = format_db_timestamp(recorded_at, pt)
            if inflow is not None:
                inflow_series.append({"x": ts, "y": inflow})
            if outflow is not None:
                outflow_series.append({"x": ts, "y": outflow})

    return inflow_series, outflow_series

def fetch_history(name, hours=24):
    """Legacy function - converts hours to days"""
    days = max(1, hours // 24)
    return fetch_history_extended(name, days)

# ---------------- CSV historical datasets (2014 to 2025) ----------------

CSV_START_DT = datetime(2014, 1, 1, 0, 0, 0)
CSV_END_DT = datetime(2025, 8, 18, 23, 59, 59)
DB_START_DT = datetime(2025, 8, 19, 0, 0, 0)

# Mapping from FFD names to CSV "Gauge Site" names
FFD_TO_CSV_NAME_MAP = {
    # Dams / reservoirs
    'TARBELA DAM': ['TARBELA'],
    'MANGLA DAM': ['MANGLA'],
    'TARBELA': ['TARBELA'],
    'MANGLA': ['MANGLA'],
    # Common headworks/barrages
    'KALABAGH': ['KALABAGH'],
    'CHASHMA': ['CHASHMA', 'CHASHMA BARRAGE'],
    'TAUNSA': ['TAUNSA', 'TAUNSA BARRAGE'],
    'GUDDU': ['GUDDU', 'GUDDU BARRAGE'],
    'SUKKUR': ['SUKKUR', 'SUKKAR', 'SUKKUR BARRAGE'],
    'KOTRI': ['KOTRI', 'KOTRI BARRAGE'],
    'KOTLI': ['KOTLI'],
    'CHATTAR KLASS': ['CHATTAR KALAS'],
    'RASUL': ['RASUL', 'RASUL BARRAGE'],
    'MARALA': ['MARALA', 'MARALA H/W'],
    'KHANKI': ['KHANKI', 'KHANKI H/W'],
    'Q.ABAD': ['QADIRABAD', 'QADIRABAD BARRAGE'],
    'QADIRABAD': ['QADIRABAD', 'QADIRABAD BARRAGE'],
    'CHINIOT': ['CHINIOT BRIDGE'],
    'TRIMMU': ['TRIMMU', 'TRIMMU H/W', 'TRIMMU H/W-'],
    'PANJNAD': ['PANJNAD', 'PUNJNAD', 'PANJNAD H/W', 'PUNJNAD H/W'],
    'PUNJNAD': ['PANJNAD', 'PUNJNAD', 'PANJNAD H/W', 'PUNJNAD H/W'],
    'JASSAR': ['JASSAR'],
    'SHAHDARA': ['SHAHDARA'],
    'BALLOKI': ['BALLOKI', 'BALLOKI H/W'],
    'SIDHNAI': ['SIDHNAI', 'SIDHNAI H/W'],
    'BHAKRA': ['BHAKRA', 'BHAKARA', 'BHAKARA**'],
    'BHAKARA': ['BHAKRA', 'BHAKARA', 'BHAKARA**'],
    'SULEMANKI': ['SULEMANKI', 'SULEIMANKI', 'SULEIMANKI H/W'],
    'ISLAM': ['ISLAM', 'ISLAM H/W'],
    'G.S WALA': ['G.S WALA*', 'G.S WALA', 'GS WALA', 'GANDA SINGH WALA'],
    'GANDA SINGH WALA': ['G.S WALA*', 'G.S WALA', 'GS WALA'],
    'KHAIRABAD': ['KHAIRABAD'],
    'ATTOCK': ['KHAIRABAD'],
    'KABUL': ['NOWSHERA','Nowshehra', 'NOWSHEHRA']
}

def normalize_name(s: str) -> str:
    """Normalize FFD/API and CSV station names to comparable canonical names."""
    if s is None:
        return ''
    text = str(s).upper().strip()
    if not text:
        return ''
    text = text.replace('**', '').replace('*', '')
    text = re.sub(r'\bH\s*/\s*W\b-?', ' ', text)
    text = re.sub(r'\bBARRAGE\b', ' ', text)
    text = re.sub(r'\bHEAD\s*WORKS?\b', ' ', text)
    text = text.replace('.', ' ')
    text = re.sub(r'[^A-Z0-9]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    compact = re.sub(r'[^A-Z0-9]+', '', text)
    aliases = {
        'QABAD': 'QADIRABAD',
        'QADIRABAD': 'QADIRABAD',
        'SUKKAR': 'SUKKUR',
        'SUKKUR': 'SUKKUR',
        'SULEIMANKI': 'SULEMANKI',
        'SULEMANKI': 'SULEMANKI',
        'PUNJNAD': 'PANJNAD',
        'PANJNAD': 'PANJNAD',
        'BHAKARA': 'BHAKRA',
        'BHAKRA': 'BHAKRA',
        'GSWALA': 'GANDA SINGH WALA',
        'GANDASINGHWALA': 'GANDA SINGH WALA',
        'CHATTARKLASS': 'CHATTAR KALAS',
        'CHATTARKALAS': 'CHATTAR KALAS',
        'NOWSHEHRA': 'NOWSHERA',
        'NOWSHERA': 'NOWSHERA'
    }
    return aliases.get(compact, text)

def parse_csv_number(val: str) -> Optional[float]:
    """Parse discharge columns from CSV: handle NR, Nil, -, blanks, commas."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    # Normalize common dash variants and punctuation
    s_norm = s.replace('—', '-').replace('–', '-').replace('\u2212', '-')
    s_lower = s_norm.lower().strip().strip(',').strip(';')
    # Treat non-numeric markers as missing
    if s_lower in {'-', '--', '---', 'nil', 'nill', 'nr', 'n/a', 'na', 'null', 'none'}:
        return None
    if s_lower.startswith('nil') or s_lower.startswith('nr'):
        return None
    # If there are no digits at all, consider it missing
    if not any(ch.isdigit() for ch in s_lower):
        return None
    # Keep digits, dot and minus; remove any other trailing units
    filtered = ''.join(ch for ch in s_norm if (ch.isdigit() or ch in ['.', '-']))
    if filtered == '' or filtered == '-' or filtered == '.':
        return None
    try:
        return float(filtered)
    except Exception:
        try:
            return float(s_norm.replace(',', ''))
        except Exception:
            return None

def csv_recorded_stamp(dt: datetime) -> str:
    """Convert datetime to a frontend-parseable timestamp with an explicit year."""
    month_map = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    return f"{dt.day:02d}-{month_map[dt.month-1]}-{dt.year} {dt.hour:02d}:{dt.minute:02d} PKT"

def get_csv_history_paths() -> List[str]:
    """Return historical CSV files in chronological load order."""
    paths = sorted(glob.glob(COMBINED_CSV_PATTERN))
    if os.path.exists(CSV_PATH):
        paths.append(CSV_PATH)
    return paths

def extract_csv_source_year(path: str) -> Optional[int]:
    match = re.search(r'(20\d{2})', os.path.basename(path))
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None

def normalize_csv_header(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', str(value or '').lower())

def csv_row_lookup(row: Dict[str, str]) -> Dict[str, str]:
    return {
        normalize_csv_header(key): val
        for key, val in row.items()
        if key is not None
    }

def csv_lookup_value(lookup: Dict[str, str], *candidate_headers: str) -> str:
    for header in candidate_headers:
        value = lookup.get(normalize_csv_header(header))
        if value is not None:
            return value
    return ''

def csv_row_value(row: Dict[str, str], *candidate_headers: str) -> str:
    return csv_lookup_value(csv_row_lookup(row), *candidate_headers)

@lru_cache(maxsize=1024)
def parse_csv_time(value: str):
    raw = str(value or '').strip()
    if not raw:
        return datetime(1900, 1, 1, 0, 0).time()
    raw = raw.replace('\xa0', ' ')
    raw = re.sub(r'\bhrs?\.?\b', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\s+', ' ', raw).strip()
    for fmt in ('%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p', '%I %p'):
        try:
            return datetime.strptime(raw, fmt).time()
        except Exception:
            continue
    return datetime(1900, 1, 1, 0, 0).time()

def parse_slash_csv_date(raw: str, source_year: Optional[int] = None) -> Optional[datetime]:
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})(?:\s+(.+))?$', raw, re.IGNORECASE)
    if not match:
        return None
    first = int(match.group(1))
    second = int(match.group(2))
    year = int(match.group(3))
    if year < 100:
        year += 2000
    time_part = match.group(4) or ''
    parsed_time = parse_csv_time(time_part)

    # The 2014 export mixes month/day slashes for days 1-12 with day-month
    # dashes after that. Other slash exports are treated as day/month.
    if first > 12:
        day, month = first, second
    elif second > 12:
        month, day = first, second
    elif source_year == 2014:
        month, day = first, second
    else:
        day, month = first, second

    try:
        return datetime(year, month, day, parsed_time.hour, parsed_time.minute, parsed_time.second)
    except Exception:
        return None

@lru_cache(maxsize=50000)
def parse_csv_datetime(date_value: str, time_value: str = '', source_year: Optional[int] = None) -> Optional[datetime]:
    date_raw = str(date_value or '').replace('\xa0', ' ').strip()
    time_raw = str(time_value or '').replace('\xa0', ' ').strip()
    if not date_raw:
        return None

    if time_raw and not re.search(r'\d{1,2}:\d{2}', date_raw):
        parsed_date = parse_csv_datetime(date_raw, '', source_year)
        if not parsed_date:
            return None
        parsed_time = parse_csv_time(time_raw)
        return datetime(
            parsed_date.year,
            parsed_date.month,
            parsed_date.day,
            parsed_time.hour,
            parsed_time.minute,
            parsed_time.second
        )

    raw = re.sub(r'\s+', ' ', date_raw).strip()
    raw = re.sub(r'\bhrs?\.?\b', '', raw, flags=re.IGNORECASE).strip()

    slash_dt = parse_slash_csv_date(raw, source_year)
    if slash_dt:
        return slash_dt

    likely_formats = []
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}', raw):
        likely_formats = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d')
    elif re.match(r'^\d{1,2}-[A-Za-z]{3}-\d{2}\b', raw):
        likely_formats = ('%d-%b-%y %H:%M:%S', '%d-%b-%y %H:%M', '%d-%b-%y')
    elif re.match(r'^\d{1,2}-[A-Za-z]{3}-\d{4}\b', raw):
        likely_formats = ('%d-%b-%Y %H:%M:%S', '%d-%b-%Y %H:%M', '%d-%b-%Y')
    elif re.match(r'^\d{1,2}-\d{1,2}-\d{4}\b', raw):
        likely_formats = ('%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%d-%m-%Y')

    fallback_formats = (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%d-%b-%Y %H:%M:%S',
        '%d-%b-%Y %H:%M',
        '%d-%b-%Y',
        '%d-%b-%y %H:%M:%S',
        '%d-%b-%y %H:%M',
        '%d-%b-%y',
        '%d-%m-%Y %H:%M:%S',
        '%d-%m-%Y %H:%M',
        '%d-%m-%Y'
    )

    for fmt in (likely_formats or fallback_formats):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue

    try:
        parsed = datetime.fromisoformat(raw)
        return parsed.replace(tzinfo=None)
    except Exception:
        return None

@lru_cache(maxsize=1)
def load_csv_history():
    """Load CSV into memory: returns dict { CSV_NAME: [ {dt, recorded, inflow, outflow, remarks} ] }"""
    data: Dict[str, List[dict]] = {}
    csv_paths = get_csv_history_paths()
    if not csv_paths:
        logging.warning(f"No historical CSV files found at {COMBINED_CSV_PATTERN} or {CSV_PATH}")
        return data

    total_rows = 0
    loaded_rows = 0
    skipped_rows = 0
    for csv_path in csv_paths:
        source_file = os.path.basename(csv_path)
        source_year = extract_csv_source_year(csv_path)
        force_source_year = source_file.startswith('combined_river_data_') and source_year is not None
        try:
            with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_rows += 1
                    try:
                        lookup = csv_row_lookup(row)
                        site = normalize_name(csv_lookup_value(lookup, 'Gauge Site', 'Gauge Sites'))
                        date_str = csv_lookup_value(lookup, 'Date')
                        time_str = csv_lookup_value(lookup, 'Time')
                        if not site or not date_str:
                            skipped_rows += 1
                            continue
                        dt = parse_csv_datetime(date_str, time_str, source_year)
                        if not dt or not (CSV_START_DT <= dt <= CSV_END_DT):
                            skipped_rows += 1
                            continue
                        if force_source_year and dt.year != source_year:
                            try:
                                dt = dt.replace(year=source_year)
                            except ValueError:
                                skipped_rows += 1
                                continue
                        inflow = parse_csv_number(csv_lookup_value(
                            lookup,
                            'Up Stream Discharge',
                            'Up Stream',
                            'Upstream'
                        ))
                        outflow = parse_csv_number(csv_lookup_value(
                            lookup,
                            'Down Stream Discharge',
                            'Down Stream',
                            'Downstream'
                        ))
                        if inflow is None and outflow is None:
                            skipped_rows += 1
                            continue
                        rec = {
                            'dt': dt,
                            'recorded': csv_recorded_stamp(dt),
                            'river': (csv_lookup_value(lookup, 'River', 'Rivers') or '').strip(),
                            'inflow': inflow,
                            'outflow': outflow,
                            'remarks': (csv_lookup_value(lookup, 'Remarks') or '').strip(),
                            'source': source_file
                        }
                        data.setdefault(site, []).append(rec)
                        loaded_rows += 1
                    except Exception as ex:
                        skipped_rows += 1
                        logging.debug(f"Skipping CSV row in {os.path.basename(csv_path)} due to parse error: {ex}")
        except Exception as e:
            logging.error(f"Failed to load CSV history from {csv_path}: {e}")

    # Sort each site's records by datetime.
    for k in list(data.keys()):
        data[k].sort(key=lambda r: r['dt'])
    logging.info(
        "Loaded CSV history for %s gauge sites from %s files (%s/%s rows loaded, %s skipped)",
        len(data),
        len(csv_paths),
        loaded_rows,
        total_rows,
        skipped_rows
    )
    return data

def csv_sites_for_ffd_name(ffd_name: str) -> List[str]:
    """Return list of CSV gauge-site names that correspond to an FFD name using mapping and heuristics."""
    if not ffd_name:
        return []
    n = normalize_name(ffd_name).replace(' DAM', '').strip()

    def unique_normalized(values) -> List[str]:
        seen = set()
        result = []
        for value in values:
            normalized = normalize_name(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    if n in FFD_TO_CSV_NAME_MAP:
        return unique_normalized(FFD_TO_CSV_NAME_MAP[n])

    # Fallback alias replacements (normalize common variants)
    aliases = {
        'SUKKAR': 'SUKKUR',
        'Q.ABAD': 'QADIRABAD',
        'Q ABAD': 'QADIRABAD',
        'CHATTAR KLASS': 'CHATTAR KALAS',
        'CHINIOT': 'CHINIOT BRIDGE',
        'PUNJNAD': 'PANJNAD',
        'GANDA SINGH WALA': 'G.S WALA*',
        'TARBELA DAM': 'TARBELA',
        'MANGLA DAM': 'MANGLA',
        'ATTOCK': 'KHAIRABAD',
        'KABUL': ['NOWSHERA', 'NOWSHEHRA']
    }
    if n in aliases:
        values = aliases[n] if isinstance(aliases[n], list) else [aliases[n]]
        return unique_normalized(values)
    # Heuristic: exact same name
    return [n]

def fetch_history_from_csv(ffd_name: str, start_dt: datetime, end_dt: datetime):
    """Fetch inflow/outflow series from CSV for the given FFD site name within [start_dt, end_dt]."""
    csv_data = load_csv_history()
    points_in, points_out = [], []
    logging.debug(f"CSV fetch: name='{ffd_name}', range={start_dt}..{end_dt}")
    if not csv_data:
        logging.debug("CSV fetch: no csv_data loaded")
        return [], []
    possible_sites = csv_sites_for_ffd_name(ffd_name)
    logging.debug(f"CSV fetch: possible sites mapped -> {possible_sites}")
    if not possible_sites:
        return [], []
    for site in possible_sites:
        records = csv_data.get(normalize_name(site), [])
        logging.debug(f"CSV fetch: site '{site}' has {len(records)} total records")
        for rec in records:                                                                                                                                                                                                                                                                               
            dt = rec['dt']
            if start_dt <= dt <= end_dt:
                if rec['inflow'] is not None:
                    points_in.append((rec['dt'], rec['recorded'], rec['inflow']))
                if rec['outflow'] is not None:
                    points_out.append((rec['dt'], rec['recorded'], rec['outflow']))
    # Ensure chronological order by actual datetime
    points_in.sort(key=lambda t: t[0])
    points_out.sort(key=lambda t: t[0])
    result_in = [{'x': rec_str, 'y': val} for (_dt, rec_str, val) in points_in]
    result_out = [{'x': rec_str, 'y': val} for (_dt, rec_str, val) in points_out]
    logging.debug(f"CSV fetch: collected {len(result_in)} inflow and {len(result_out)} outflow points")
    return result_in, result_out

def fetch_all_stations_history(start_date: Optional[str] = None, end_date: Optional[str] = None, days: Optional[int] = None) -> Dict[str, Dict[str, List[dict]]]:
    """Fetch combined CSV + Database historical data for ALL stations.
    - If start_date and end_date are provided: filters by date range.
    - Else if days is provided: filters by last N days.
    - Else (no params): returns ALL historical data (2014 to present).
    """
    if start_date and end_date:
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        except Exception:
            s_dt = CSV_START_DT
            e_dt = datetime.utcnow()
    elif days is not None:
        e_dt = datetime.utcnow()
        s_dt = e_dt - timedelta(days=int(days))
    else:
        s_dt = CSV_START_DT
        e_dt = datetime.utcnow()

    stations_data: Dict[str, Dict[str, List[dict]]] = {}

    # 1. Process CSV portion
    csv_s = max(s_dt, CSV_START_DT)
    csv_e = min(e_dt, CSV_END_DT)
    if csv_s <= csv_e:
        csv_history = load_csv_history()
        for site_name, records in csv_history.items():
            st_key = site_name.upper().strip()
            st_entry = stations_data.setdefault(st_key, {'inflow': [], 'outflow': []})
            for rec in records:
                dt = rec['dt']
                if csv_s <= dt <= csv_e:
                    rec_str = rec['recorded']
                    if rec['inflow'] is not None:
                        st_entry['inflow'].append({'x': rec_str, 'y': rec['inflow']})
                    if rec['outflow'] is not None:
                        st_entry['outflow'].append({'x': rec_str, 'y': rec['outflow']})

    # 2. Process Database portion
    db_s = max(s_dt, DB_START_DT)
    db_e = e_dt
    if db_s <= db_e:
        with DB_LOCK:
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT name, inflow_discharge, outflow_discharge, recorded_at, fetched_at
                    FROM telemetry_history
                    WHERE recorded_at IS NOT NULL
                    ORDER BY fetched_at ASC
                    """
                )
                rows = cur.fetchall()
                conn.close()
            except sqlite3.Error:
                rows = []

        for db_name, inflow, outflow, recorded_at, fetched_at in rows:
            st_key = db_name.upper().strip()
            for ffd_key in FFD_TO_CSV_NAME_MAP:
                if normalize_name(db_name) == normalize_name(ffd_key):
                    mapped_sites = FFD_TO_CSV_NAME_MAP[ffd_key]
                    if mapped_sites:
                        st_key = mapped_sites[0].upper().strip()
                    break

            fallback_year = None
            try:
                fallback_year = datetime.fromisoformat(fetched_at).year if fetched_at else None
            except Exception:
                fallback_year = None

            pt = parse_recorded_at(recorded_at, fallback_year)
            if not pt:
                continue

            if db_s <= pt <= db_e:
                ts = format_db_timestamp(recorded_at, pt)
                st_entry = stations_data.setdefault(st_key, {'inflow': [], 'outflow': []})
                if inflow is not None:
                    st_entry['inflow'].append({'x': ts, 'y': inflow})
                if outflow is not None:
                    st_entry['outflow'].append({'x': ts, 'y': outflow})

    return stations_data

@app.route('/api/history-csv')
def get_history_csv_only():
    """Return only CSV historical data for a site between dates (for debugging/verification)."""
    name = request.args.get('name')
    start_date = request.args.get('start_date')  # YYYY-MM-DD
    end_date = request.args.get('end_date')      # YYYY-MM-DD
    if not name or not start_date or not end_date:
        return jsonify({'success': False, 'error': 'name, start_date, end_date are required'}), 400
    try:
        s_dt = datetime.strptime(start_date, "%Y-%m-%d")
        e_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Invalid date range: {e}'}), 400
    # Intersect with CSV window
    s_dt = max(s_dt, CSV_START_DT)
    e_dt = min(e_dt, CSV_END_DT)
    inflow, outflow = ([], [])
    if s_dt <= e_dt:
        inflow, outflow = fetch_history_from_csv(name, s_dt, e_dt)
    return jsonify({
        'success': True,
        'name': name,
        'start_date': start_date,
        'end_date': end_date,
        'csv_window_start': CSV_START_DT.isoformat(),
        'csv_window_end': CSV_END_DT.isoformat(),
        'inflow': inflow,
        'outflow': outflow,
        'csv_points': { 'inflow': len(inflow), 'outflow': len(outflow) }
    })

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

@app.route('/api/history-all')
def get_all_history():
    """Get historical data for ALL stations combined from CSV + Database."""
    start_date = request.args.get('start_date')  # YYYY-MM-DD
    end_date = request.args.get('end_date')      # YYYY-MM-DD
    days = request.args.get('days')
    days_val = int(days) if days else None
    stations_data = fetch_all_stations_history(start_date, end_date, days=days_val)
    return jsonify({
        'success': True,
        'start_date': start_date,
        'end_date': end_date,
        'days': days_val,
        'total_stations': len(stations_data),
        'source': 'csv+database',
        'stations': stations_data
    })

@app.route('/api/history')
def get_history():
    """Get historical data from database (read-only). If name is omitted or 'all', returns all stations."""
    name = request.args.get('name')
    days_arg = request.args.get('days')
    days_val = int(days_arg) if days_arg else None
    hours = int(request.args.get('hours', (days_val or 15) * 24))
    start_date = request.args.get('start_date')  # YYYY-MM-DD
    end_date = request.args.get('end_date')      # YYYY-MM-DD
    
    if not name or name.strip().lower() in ('all', '*', 'all_stations'):
        stations_data = fetch_all_stations_history(start_date, end_date, days=days_val)
        return jsonify({
            'success': True,
            'start_date': start_date,
            'end_date': end_date,
            'days': days_val,
            'total_stations': len(stations_data),
            'source': 'csv+database',
            'stations': stations_data
        })
    
    # If explicit date range provided, use it (merge CSV [Jun 15..Aug 18] + DB [Aug 19..])
    if start_date and end_date:
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Invalid date range: {e}'}), 400

        # CSV portion intersection
        csv_in, csv_out = [], []
        csv_s = max(s_dt, CSV_START_DT)
        csv_e = min(e_dt, CSV_END_DT)
        logging.info(f"History: {name} requested {s_dt}..{e_dt}; CSV window {csv_s}..{csv_e}")
        if csv_s <= csv_e:
            csv_in, csv_out = fetch_history_from_csv(name, csv_s, csv_e)

        # DB portion intersection
        db_in, db_out = [], []
        db_s = max(s_dt, DB_START_DT)
        db_e = e_dt
        logging.info(f"History: {name} DB window {db_s}..{db_e}")
        if db_s <= db_e:
            db_in, db_out = fetch_history_between(name, db_s.strftime('%Y-%m-%d'), db_e.strftime('%Y-%m-%d'))

        inflow_series = (csv_in or []) + (db_in or [])
        outflow_series = (csv_out or []) + (db_out or [])
        logging.info(f"History: {name} returning {len(inflow_series)} inflow, {len(outflow_series)} outflow points (CSV {len(csv_in)}/{len(csv_out)}, DB {len(db_in)}/{len(db_out)})")
        return jsonify({
            'success': True,
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'inflow': inflow_series,
            'outflow': outflow_series,
            'points': max(len(inflow_series), len(outflow_series)),
            'source': 'csv+database' if (csv_in or csv_out) else 'database_readonly'
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

@app.route('/api/storage-history')
def get_storage_history():
    """Get reservoir storage history from daily_water_situation.sqlite"""
    name = request.args.get('name', '').strip()
    days = int(request.args.get('days', 30))
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not name:
        return jsonify({'success': False, 'error': 'Missing name parameter'}), 400

    # Map station name to reservoir name
    norm = name.lower()
    if 'tarbela' in norm:
        reservoir = 'Tarbela'
    elif 'mangla' in norm:
        reservoir = 'Mangla'
    elif 'chashma' in norm:
        reservoir = 'Chashma'
    else:
        return jsonify({'success': False, 'error': f'No reservoir storage data for station: {name}'}), 404

    if not os.path.exists(DAILY_WATER_DB_PATH):
        return jsonify({'success': False, 'error': f'Database not found at {DAILY_WATER_DB_PATH}'}), 404

    try:
        conn = sqlite3.connect(DAILY_WATER_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if start_date and end_date:
            cur.execute("""
                SELECT recorded_date, today, last_year, avg_last_5_years, avg_last_10_years, max_maf
                FROM reservoir_storages
                WHERE reservoir = ? AND recorded_date >= ? AND recorded_date <= ?
                ORDER BY recorded_date ASC
            """, (reservoir, start_date, end_date))
        else:
            # Fetch last N days relative to the latest available date
            cur.execute("SELECT MAX(recorded_date) FROM reservoir_storages WHERE reservoir = ?", (reservoir,))
            latest_row = cur.fetchone()
            latest_date = latest_row[0] if latest_row else None
            if not latest_date:
                conn.close()
                return jsonify({'success': True, 'reservoir': reservoir, 'series': [], 'max_maf': None})

            from datetime import datetime as _dt, timedelta as _td
            latest_dt = _dt.strptime(latest_date, '%Y-%m-%d')
            cutoff_dt = latest_dt - _td(days=days - 1)
            cutoff_str = cutoff_dt.strftime('%Y-%m-%d')

            cur.execute("""
                SELECT recorded_date, today, last_year, avg_last_5_years, avg_last_10_years, max_maf
                FROM reservoir_storages
                WHERE reservoir = ? AND recorded_date >= ?
                ORDER BY recorded_date ASC
            """, (reservoir, cutoff_str))

        rows = cur.fetchall()
        conn.close()

        series = []
        max_maf = None
        for row in rows:
            rec_date, today_val, last_year, avg5, avg10, maf = row
            if max_maf is None and maf is not None:
                max_maf = float(maf)
            series.append({
                'date': rec_date,
                'today': float(today_val) if today_val is not None else None,
                'last_year': float(last_year) if last_year is not None else None,
                'avg_last_5_years': float(avg5) if avg5 is not None else None,
                'avg_last_10_years': float(avg10) if avg10 is not None else None,
            })

        return jsonify({
            'success': True,
            'reservoir': reservoir,
            'max_maf': max_maf,
            'series': series,
            'points': len(series)
        })

    except Exception as e:
        logging.error(f"Error fetching storage history for {name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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

@app.route('/api/daily-situation')
def get_daily_situation():
    station_name = request.args.get('station')
    if not station_name:
        return jsonify({'success': False, 'error': 'Missing station parameter'}), 400
        
    if not os.path.exists(DAILY_WATER_DB_PATH):
        return jsonify({'success': False, 'error': f'Database not found at {DAILY_WATER_DB_PATH}'}), 404
        
    try:
        conn = sqlite3.connect(DAILY_WATER_DB_PATH)
        cursor = conn.cursor()
        
        # Get the latest report date and calculate yesterday as exactly 1 day prior
        cursor.execute("SELECT report_date FROM daily_water_reports ORDER BY report_date DESC LIMIT 1;")
        dates = [r[0] for r in cursor.fetchall()]
        
        if len(dates) < 1:
            conn.close()
            return jsonify({'success': False, 'error': 'No daily water report dates in database'}), 500
            
        d1 = dates[0]
        latest_dt = datetime.strptime(d1, "%Y-%m-%d")
        yesterday_dt = latest_dt - timedelta(days=1)
        d2 = yesterday_dt.strftime("%Y-%m-%d")
        
        # Normalize name for generic matching
        norm = station_name.lower().strip()
        norm = re.sub(r'\s+dam$', '', norm)
        norm = re.sub(r'\s+barrage$', '', norm)
        norm = norm.strip()
        
        def fetch_all_dict(query, params):
            cursor.execute(query, params)
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
            
        skardu_temp = []
        res_levels = []
        res_storages = []
        barrages_discharge = []
        river_inflows = []
        
        # 1. Skardu temperature
        if "skardu" in norm:
            skardu_temp = fetch_all_dict(
                "SELECT * FROM skardu_temperature WHERE recorded_date IN (?, ?) ORDER BY recorded_date DESC, row_order ASC;",
                (d1, d2)
            )
            
        # 2. Reservoir Levels & Storages
        res_name = None
        if "tarbela" in norm:
            res_name = "Tarbela"
        elif "mangla" in norm:
            res_name = "Mangla"
        elif "chashma" in norm:
            res_name = "Chashma"
            
        if res_name:
            res_levels = fetch_all_dict(
                "SELECT * FROM reservoir_levels WHERE reservoir = ? AND recorded_date IN (?, ?) ORDER BY recorded_date DESC;",
                (res_name, d1, d2)
            )
            res_storages = fetch_all_dict(
                "SELECT * FROM reservoir_storages WHERE reservoir = ? AND recorded_date IN (?, ?) ORDER BY recorded_date DESC;",
                (res_name, d1, d2)
            )
            
        # 3. Barrages Discharge
        barrage_name = None
        if "guddu" in norm:
            barrage_name = "Guddu"
        elif "kotri" in norm:
            barrage_name = "Kotri"
        elif "panjnad" in norm:
            barrage_name = "Panjnad"
        elif "sukkur" in norm:
            barrage_name = "Sukkur"
        elif "taunsa" in norm:
            barrage_name = "Taunsa"
        elif "trimmu" in norm:
            barrage_name = "Trimmu"
        elif "jinnah" in norm or "kalabagh" in norm:
            barrage_name = "Jinnah (Mean 24 hrs)"
        elif "chashma" in norm:
            barrage_name = "Chashma (Mean 24 hrs)"
            
        if barrage_name:
            barrages_discharge = fetch_all_dict(
                "SELECT * FROM barrages_discharge WHERE station = ? AND recorded_date IN (?, ?) ORDER BY recorded_date DESC;",
                (barrage_name, d1, d2)
            )
            
        # 4. River Inflows
        inflow_name = None
        if "tarbela" in norm:
            inflow_name = "Indus at Tarbela"
        elif "mangla" in norm:
            inflow_name = "Jhelum at Mangla"
        elif "marala" in norm:
            inflow_name = "Chenab at Marala"
        elif "nowshera" in norm or "kabul" in norm:
            inflow_name = "Kabul at Nowshera"
            
        if inflow_name:
            river_inflows = fetch_all_dict(
                "SELECT * FROM river_inflows WHERE station LIKE ? AND recorded_date IN (?, ?) ORDER BY recorded_date DESC;",
                (f"%{inflow_name}%", d1, d2)
            )
            
        conn.close()
        
        return jsonify({
            'success': True,
            'station': station_name,
            'latest_date': d1,
            'yesterday_date': d2,
            'skardu_temp': skardu_temp,
            'reservoir_levels': res_levels,
            'reservoir_storages': res_storages,
            'barrages_discharge': barrages_discharge,
            'river_inflows': river_inflows
        })
        
    except Exception as e:
        logging.error(f"Error querying daily situation for {station_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
