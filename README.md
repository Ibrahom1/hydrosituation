# Hydrological Situation Dashboard

A compact hydrology dashboard stack for dams and headworks:
- Frontend: `index.html`, `script.js`, `styles.css`
- Backend API: `backend/app.py`
- Collector: `remote_collector.py`
- Scheduler: `.github/workflows/remote-collector.yml`

## What This Repo Does

- Fetches PM dashboard telemetry (`https://ffd.pmd.gov.pk/api/pm-dashboard`)
- Stores snapshots in `hydro_history.db` and `latest.json`
- Serves current and historical data through Flask endpoints
- Renders dam/headwork charts and tables in the frontend

## Core Files

- `backend/app.py`: API server (`/api/ffd-dams`, `/api/ffd-headworks`, `/api/history`, `/api/health`)
- `remote_collector.py`: PM-only collector (default one attempt)
- `.github/workflows/remote-collector.yml`: scheduled collector run on self-hosted runner
- `historic2025flooddata_16june.csv`: baseline historical CSV

## Quick Start

1. Backend

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

```bash
pip install -r requirements.txt
python app.py
```

2. Frontend

Open `index.html` directly, or serve statically:

```bash
python -m http.server 8080
```

3. Collector (manual)

```bash
python remote_collector.py
```

## Required Configuration

Create `.env` from `.env.example` and set:
- `FFD_API_KEY=<your_api_key>`

Optional:
- `REMOTE_DATA_URL`
- `PORT`

## Workflow Notes

- The collector workflow is scheduled daily at `03:00 UTC`.
- It is configured for self-hosted runner labels:
  - `self-hosted`, `linux`, `x64`, `ffd-linux`
- It logs runner public egress IP (`api.ipify.org`) for allowlisting checks.

## Troubleshooting (Short)

- 403 with HTML "Just a moment...": usually WAF/Cloudflare challenge; use self-hosted runner/IP allowlisting.
- No history in charts: check `hydro_history.db` exists and backend is running on `http://localhost:5000`.
- No updates committed by workflow: check `FFD_API_KEY` secret and runner online status.
