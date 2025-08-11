# Hydrological Dashboard 🌊

A real-time hydrological monitoring dashboard for dams and headworks across Pakistan's major river systems.

## 🌟 Features

### 📊 **Real-time Monitoring**
- **Dams**: Mangla, Tarbela, Warsak, Khanpur with live telemetry
- **Headworks**: Organized by river systems (INDUS, JHELUM, CHENAB, RAVI, SUTLEJ, KABUL)
- **Inflow/Outflow Trends**: Visual trend indicators with color-coded status
- **Historical Data**: Automatic collection every 6 hours with persistent storage

### 🗺️ **River-based Organization**
- **INDUS**: Sukkur Barrage, Kotri Barrage, Taunsa Barrage
- **JHELUM**: Rasul Barrage, Qadirabad Barrage  
- **CHENAB**: Khanki Barrage, Qadirabad Barrage
- **RAVI**: Balloki Barrage, Sidhnai Barrage
- **SUTLEJ**: Suleimanki Barrage, Islam Barrage
- **KABUL**: Warsak Dam area structures
- **OTHER**: Remaining headworks (sorted at bottom)

### � **Automated Data Collection**
- **Schedule**: Every 6 hours (00:00, 06:00, 12:00, 18:00 PKT)
- **Source**: FFD (Flood Forecasting Division) Live Telemetry
- **Storage**: SQLite database with automatic cleanup
- **Fallback**: Synthetic data generation when API unavailable

## Tech Stack

### Backend
- **Framework**: Python Flask with APScheduler
- **Database**: SQLite with historical data storage
- **Scheduling**: APScheduler for 6-hour data collection
- **APIs**: FFD Telemetry integration with timeout handling

### Frontend
- **Framework**: HTML5, CSS3, JavaScript (ES6+)
- **Charts**: Chart.js for time-series visualization
- **Icons**: Font Awesome for trend indicators
- **Responsive**: CSS Grid and Flexbox

### Data Flow
- **External API**: FFD Telemetry (60s timeout with fallback)
- **Historical Storage**: SQLite with timestamp indexing
- **Real-time Updates**: Fetch API with error handling
- **Chart Updates**: Dynamic data injection into Chart.js

## Quick Start

### Backend Setup:
```bash
cd backend
pip install -r requirements.txt
python app.py
```

### Frontend Setup:
```bash
cd ..
python -m http.server 8080
```

### Access Dashboard:
- Frontend: http://localhost:8080
- Backend API: http://localhost:5000/api/health

## File Structure
```
hydro-dashboard/
```
hydro-dashboard/
├── index.html              # Main dashboard interface
├── script.js              # Frontend JavaScript with Chart.js
├── styles.css             # CSS styling with trend indicators
├── config.js              # API configuration
├── README.md             # This file
└── backend/              # Flask backend
    ├── app.py           # Main Flask app with APScheduler
    ├── requirements.txt # Python dependencies
    ├── hydro_history.db    # SQLite historical data
    └── uploads/         # Media upload directory
```

## API Endpoints

### Current Data
- `GET /api/ffd-dams` - Live dam telemetry
- `GET /api/ffd-headworks` - Live headworks telemetry
- `GET /api/telemetry` - Combined current data
- `GET /api/health` - System health check

### Historical Data
- `GET /api/history?name={name}&hours={hours}` - Time-series data
- **Parameters**: 
  - `name`: Dam/headwork name
  - `hours`: Hours of history (default: 24)
- **Returns**: `{inflow: [...], outflow: [...]}`

### Data Collection
- **Automatic**: Every 6 hours via APScheduler
- **Manual**: Triggered on app startup
- **Storage**: SQLite with unique timestamps
- **Cleanup**: Old data automatically managed

## 📊 Data Visualization

### Chart Features
- **Time-series**: Inflow/outflow trends over time
- **Responsive**: Auto-adjusts to screen size
- **Interactive**: Hover for exact values
- **Real-time**: Updates with fresh data
- **Fallback**: Synthetic data when API unavailable

### Trend Indicators
- 🟢 **Rising**: Increasing trend (green pill)
- 🔴 **Falling**: Decreasing trend (red pill)  
- ⚫ **Steady**: Stable levels (gray pill)
- 📈 **Historical**: Chart icon for time-series

## 🔧 Configuration

### Configuration

Modify schedule in `backend/app.py`:
```python
scheduler.add_job(
    func=scheduled_job,
    trigger="interval", 
    hours=6,  # Change frequency here
    id='telemetry_job'
)
```

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

### Data Collection
- **Frequency**: Every 6 hours automatically
- **Source**: FFD Live Telemetry with 60s timeout
- **Fallback**: Synthetic data when API unavailable
- **Storage**: SQLite with indexed timestamps

### Error Handling
- **API Timeouts**: 60-second timeout with graceful fallback
- **Missing Data**: Synthetic data generation for continuity
- **Database Locks**: Thread-safe operations with automatic retry
- **Network Issues**: Cached data serving during outages

### Performance
- **Efficient Queries**: Indexed database operations
- **Minimal Payload**: Optimized API responses
- **Client Caching**: Smart data refresh intervals
- **Background Jobs**: Non-blocking scheduled operations

## License
MIT License - Feel free to use and modify for water management purposes.

---

**Built for Pakistan's Water Resource Management** 🇵🇰
