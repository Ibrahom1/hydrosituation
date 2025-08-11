#!/usr/bin/env python3
"""Remote collector script (resilient).
Primary attempt: public endpoints ffd.gov.pk/api/dams & /api/headworks.
Fallback: pm-dashboard POST endpoint (requires API key) -> derive dams & headworks.
Graceful behaviour: if all attempts fail (DNS / network), exit 0 without updating file (prevents red workflow) and print SKIP.

Environment variables:
  FFD_API_KEY  (optional) API key for fallback endpoint https://ffd.pmd.gov.pk/api/pm-dashboard
  MAX_ATTEMPTS (optional) retry attempts for each fetch (default 5)
"""

import json, sys, requests, datetime, time, os
from requests.exceptions import RequestException

FFD_DAMS = 'https://ffd.gov.pk/api/dams'
FFD_HEADWORKS = 'https://ffd.gov.pk/api/headworks'
PM_DASHBOARD = 'https://ffd.pmd.gov.pk/api/pm-dashboard'

OUT_FILE = 'latest.json'
API_KEY = os.environ.get('FFD_API_KEY', '').strip()
MAX_ATTEMPTS = int(os.environ.get('MAX_ATTEMPTS', '5'))

UA = {'User-Agent': 'HybridHydroCollector/1.1'}

def retry_fetch_json(method, url, **kwargs):
    """Generic retry wrapper."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.request(method, url, timeout=60, headers=UA, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            wait = attempt * 2
            print(f'[WARN] Attempt {attempt}/{MAX_ATTEMPTS} failed for {url}: {e}. Retrying in {wait}s...')
            time.sleep(wait)
    raise RuntimeError(f'All {MAX_ATTEMPTS} attempts failed for {url}')

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

def write_payload(dams, headworks):
    payload = {
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'dams': dams,              # {"dams": [...]}
        'headworks': headworks     # {"headworks": [...]} 
    }
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f'[OK] Wrote {OUT_FILE}: dams={len(dams.get("dams", []))} headworks={len(headworks.get("headworks", []))}')

def main():
    # Phase 1: public endpoints
    try:
        print('[INFO] Trying public endpoints (ffd.gov.pk)...')
        dams, headworks = fetch_public_split()
        write_payload(dams, headworks)
        return 0
    except Exception as pub_err:
        print(f'[WARN] Public endpoints failed: {pub_err}')

    # Phase 2: fallback dashboard
    try:
        print('[INFO] Trying fallback pm-dashboard endpoint...')
        dams, headworks = fetch_via_dashboard()
        write_payload(dams, headworks)
        return 0
    except Exception as dash_err:
        print(f'[WARN] Fallback dashboard failed: {dash_err}')
        print('[SKIP] No data collected this run (network or API issue). Workflow will succeed without update.')
        return 0  # graceful success to avoid red X

if __name__ == '__main__':
    sys.exit(main())

if __name__ == '__main__':
    raise SystemExit(main())
