# Hydrological Situation Dashboard

This project provides a frontend dashboard plus a Flask API backend for monitoring Pakistan hydrological telemetry (dams and headworks), including historical charts and date-range filtering.

The repository currently uses:
- A read-only backend API that fetches and caches live telemetry from PM Dashboard
- A remote collector script that writes `latest.json` and `hydro_history.db`
- A GitHub Actions workflow running on a self-hosted Linux runner

## What Is In This Folder

- `index.html`, `styles.css`, `script.js`, `config.js`: frontend dashboard
- `backend/app.py`: Flask API server
- `backend/requirements.txt`: backend dependencies
- `remote_collector.py`: PM dashboard collector that updates JSON and SQLite
- `.github/workflows/remote-collector.yml`: scheduled collector workflow
- `historic2025flooddata_16june.csv`: CSV history source (June to August 2025)
- `latest.json`: latest collector payload for remote sync
- `hydro_history.db`: SQLite history database maintained by collector

## Current Data Flow

1. `remote_collector.py` calls `https://ffd.pmd.gov.pk/api/pm-dashboard` using `FFD_API_KEY`.
2. Collector writes:
   - `latest.json`
   - `hydro_history.db` (`telemetry_history` table)
3. Backend serves frontend from cache and API endpoints.
4. Frontend calls backend endpoints on `http://localhost:5000` and renders charts/tables.

## Runtime Components

### Frontend

- UI: vanilla HTML/CSS/JS
- Charts: Chart.js with annotation and zoom plugins
- Main features:
  - Dams and headworks panels
  - Chart/table toggle per section
  - Date range apply/reset controls
  - Peak outflow display per chart
  - River-grouped headworks view

The frontend can optionally request backend remote sync via:
- `window.REMOTE_DATA_URL` in `index.html`

### Backend (`backend/app.py`)

Backend mode is read-only for persistence; it does not write telemetry snapshots itself.

Key behaviors:
- Loads `FFD_API_KEY` from environment (`python-dotenv`)
- Fetches PM dashboard data and caches in memory
- Uses SQLite (`hydro_history.db`) for historical reads
- Merges CSV history and DB history for date-range queries

Main endpoints:
- `GET /api/health`
- `GET /api/ffd-telemetries`
- `GET /api/ffd-dams`
- `GET /api/ffd-headworks`
- `GET /api/history?name=<site>&days=15`
- `GET /api/history?name=<site>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /api/history-csv?name=<site>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /api/storage-status`
- `GET /api/sync-remote?url=<remote-json-url>`

### Remote Collector (`remote_collector.py`)

Collector behavior is currently PM-dashboard-only.

Key points:
- Endpoint: `https://ffd.pmd.gov.pk/api/pm-dashboard`
- Auth payload: `API_KEY` form field
- Default retries: `MAX_ATTEMPTS=1`
- Graceful failure policy:
  - logs warning and skip reason
  - writes placeholder `latest.json` if file does not exist
  - exits with code `0` to avoid breaking CI on transient network/auth issues
- Writes to SQLite table `telemetry_history`

## Environment Variables

### Backend

Set in `.env` (copy from `.env.example`):

- `FFD_API_KEY`: required for live PM dashboard fetches
- `PORT`: optional, defaults to `5000`
- `REMOTE_DATA_URL`: optional URL used by `/api/sync-remote`

### Collector

- `FFD_API_KEY`: required for PM dashboard endpoint
- `MAX_ATTEMPTS`: optional, default `1`
- `DB_PATH`: optional, default `hydro_history.db`

## Local Setup

## 1) Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies and run:

```bash
pip install -r requirements.txt
python app.py
```

Backend default URL:
- `http://localhost:5000`

## 2) Frontend

Open `index.html` directly or serve with a local static server.

Example from `waterdashboard` directory:

```bash
python -m http.server 8080
```

Then open:
- `http://localhost:8080`

## 3) Run Collector Manually

From `waterdashboard` directory:

```bash
python remote_collector.py
```

## GitHub Actions Workflow

Workflow file:
- `.github/workflows/remote-collector.yml`

Current workflow configuration:
- Schedule: daily at `03:00 UTC` (`08:00 Karachi`)
- Runner labels:
  - `self-hosted`
  - `linux`
  - `x64`
  - `ffd-linux`
- Logs runner public egress IP using `https://api.ipify.org`
- Runs collector with `MAX_ATTEMPTS=1`
- Commits updates to `latest.json` and `hydro_history.db`

Important:
- `FFD_API_KEY` must be configured in repository secrets.

## Self-Hosted Runner Notes

Because PM dashboard requests may be blocked on cloud datacenter IPs, this repository is configured for a self-hosted runner.

Checklist:
- Runner machine stays online at scheduled run time
- Outbound HTTPS (`443`) to GitHub is available
- API owner can allowlist your runner egress IP if required

## Troubleshooting

### PM dashboard returns HTML "Just a moment..." with 403

This usually indicates Cloudflare/WAF challenge at the source endpoint.

Actions:
- use self-hosted runner with stable egress IP
- request API-side IP allowlisting
- verify `FFD_API_KEY` secret is set and non-empty

### No history shown on charts

Check:
- backend is running on `http://localhost:5000`
- `hydro_history.db` exists in `waterdashboard`
- `GET /api/storage-status` returns valid record counts

### Frontend shows stale data

Use Refresh button and check backend logs for:
- PM API fetch errors
- remote sync failures
- cache fallback behavior

## Notes on Included Test Script

`backend/test_ffd_api.py` is a manual connectivity/debug script. It currently contains a hardcoded token placeholder pattern and should be treated as local diagnostic code only.

Recommended practice:
- avoid hardcoded credentials
- load token from environment before sharing or committing updates

## Project Structure

```text
waterdashboard/
  .env.example
  .github/workflows/remote-collector.yml
  backend/
    app.py
    requirements.txt
    test_ffd_api.py
  config.js
  historic2025flooddata_16june.csv
  index.html
  latest.json
  ndma-logo.png
  README.md
  remote_collector.py
  script.js
  styles.css
```
