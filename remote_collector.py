#!/usr/bin/env python3
"""Remote collector script.
Fetches FFD endpoints and writes latest.json (compact public artifact).
Designed to run inside GitHub Actions every 6 hours.
"""
import json, sys, requests, datetime

FFD_DAMS = 'https://ffd.gov.pk/api/dams'
FFD_HEADWORKS = 'https://ffd.gov.pk/api/headworks'

OUT_FILE = 'latest.json'

def fetch(url):
    r = requests.get(url, timeout=60, headers={'User-Agent':'HybridHydroCollector/1.0'})
    r.raise_for_status()
    return r.json()

def main():
    try:
        dams = fetch(FFD_DAMS)
        headworks = fetch(FFD_HEADWORKS)
        payload = {
            'generated_at': datetime.datetime.utcnow().isoformat()+'Z',
            'dams': dams,            # keep original structure {"dams": [...]} 
            'headworks': headworks   # {"headworks": [...]} 
        }
        with open(OUT_FILE,'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
        print(f'Wrote {OUT_FILE} with {len(dams.get("dams",[]))} dams and {len(headworks.get("headworks",[]))} headworks.')
    except Exception as e:
        print('ERROR:', e, file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
