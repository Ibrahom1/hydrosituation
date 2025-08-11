# Hydrological Situation Dashboard 🌊

Minimal real-time hydrological monitoring dashboard for Pakistan's major dams & headworks with: 
* Local Flask API (FFD telemetries + 6‑hour history collection)
* Optional hybrid remote collector (GitHub Actions) producing a `latest.json` you can sync when your PC is off
* Lightweight frontend (HTML + Chart.js) – no build step

## 🌟 Features

### 📊 **Real-time Monitoring**
- Dams & headworks classified automatically (river-based grouping for headworks)
- Inflow / outflow values with simple trend fields (as provided by source)
- Historical snapshots every 6 hours stored in SQLite

### 🗺️ **River-based Organization**
Headworks are auto‑bucketed into INDUS / JHELUM / CHENAB / RAVI / SUTLEJ / KABUL / OTHER using flexible name matching.

### ♻️ **Automated Data Collection**
- Interval: every 6 hours (scheduler starts immediately then every 6h)
- Source: FFD (PM Dashboard endpoint) using `FFD_API_KEY`
- Storage: SQLite table `telemetry_history`
- Fallback: serves last cached or empty arrays (no synthetic generation now)

## Tech Stack

### Backend
- Flask + APScheduler
- SQLite for historical snapshots
- `.env` driven config (FFD_API_KEY, optional REMOTE_DATA_URL)

### Frontend
- Vanilla HTML/CSS/JS (Chart.js + date-fns adapter)
- `config.js` handles remote sync attempt then falls back to local API

### Data Flow
1. (Optional) GitHub Actions runs `remote_collector.py` every 6h -> commits `latest.json`.
2. Frontend on load calls `/api/sync-remote` (if REMOTE_DATA_URL set) to pull remote snapshot into local DB.
3. Local backend scheduler also fetches directly every 6h when running.
4. Endpoints serve current cached set + history.

## Quick Start

### Backend Setup
```powershell
cd backend
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
copy ..\.env.example ..\.env  # then edit FFD_API_KEY
python app.py
```

### Frontend (Static)
Open `index.html` directly or serve folder:
```powershell
cd ..
python -m http.server 8080
```

Visit:
- Frontend: http://localhost:8080
- Health:   http://localhost:5000/api/health

## File Structure
```
repo/
├── index.html        # Dashboard UI
├── script.js         # Frontend logic & charts
├── styles.css        # Styling
├── config.js         # Remote sync + API base
├── latest.json       # (Optional) remote snapshot (ignored if empty)
├── remote_collector.py # Script used by GitHub Actions workflow
├── .env.example      # Template for environment vars
└── backend/
  ├── app.py
  ├── requirements.txt
  └── hydro_history.db (created at runtime)
```

## API Endpoints

### Current Data
- `GET /api/ffd-dams`       - Current dams (cached)
- `GET /api/ffd-headworks`  - Current headworks grouped by river
- `GET /api/ffd-telemetries`- Combined list
- `GET /api/history?name=Kalabagh&hours=24` - Time‑series for a site
- `GET /api/sync-remote`    - Pull remote latest.json into local DB
- `GET /api/health`         - Health check

History endpoint returns two series arrays: inflow & outflow (x=ISO timestamp, y=value).

### Data Collection
Local scheduler + optional remote JSON (choose either or both). No upload/media features.

## 📊 Data Visualization

### Charts
Time‑series inflow/outflow, responsive, hover tooltip, dynamic refresh button.

Trend fields (`inflow_trend`, `outflow_trend`) are passed through from source (styling handled in frontend).

## 🔧 Configuration

### Schedule Change
Edit `scheduler.add_job(... hours=6 ...)` in `backend/app.py` to adjust frequency.

### Environment Variables (`.env`)
```
FFD_API_KEY=your_token_here
REMOTE_DATA_URL=https://raw.githubusercontent.com/<user>/<repo>/main/latest.json  # optional
```
If REMOTE_DATA_URL omitted, `/api/sync-remote` needs `?url=` param to test.

## 🤝 Contributing

1. Fork or download the project
2. Create feature branch
3. Make your changes
4. Test locally
5. Share your improvements

## 📞 Support

For issues or questions:
- Create an issue or discussion
- Review API endpoints at `/api/health`

## 🔄 Automatic Features

Data fetch every 6h (local) + optional remote sync; serves stale cache if live fetch fails.

### Error Handling
- API timeout (60s) -> raises; cache served if present
- Missing token -> warning logged; fetch endpoints will return empty until set
- Thread safety via single Lock around DB writes

### Performance
Lightweight single-process Flask + in-memory latest cache + periodic DB inserts.

## License
MIT License - Use and adapt freely.

---

**Built for Pakistan's Water Resource Management** 🇵🇰
