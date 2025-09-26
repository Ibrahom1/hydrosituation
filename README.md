# 🌊 Hydrological Situation Dashboard

A modern, real-time hydrological monitoring dashboard for Pakistan's major dams and headworks featuring an enhanced UI with 3D visual elements, smooth animations, and comprehensive data visualization.

![Dashboard Preview](https://img.shields.io/badge/Status-Active-brightgreen) ![Node.js](https://img.shields.io/badge/Frontend-Vanilla_JS-yellow) ![Python](https://img.shields.io/badge/Backend-Flask-blue) ![License](https://img.shields.io/badge/License-MIT-green)

## 🚀 Features

### 📊 **Real-time Data Monitoring**
- **Live telemetry data** from Pakistan's major dams and headworks
- **Real-time inflow/outflow** discharge monitoring
- **Historical data tracking** with hourly interval snapshots
- **River-based organization** (INDUS, JHELUM, CHENAB, RAVI, SUTLEJ, KABUL)
- **Automated data classification** between dams and headworks

### 🎨 **Modern User Interface**
- **3D glassmorphism effects** with backdrop blur and depth shadows
- **Smooth animations** with progressive line drawing (stock-market style)
- **Grid-free charts** with clean axis-only visualization  
- **Responsive design** optimized for all device sizes
- **Interactive charts** with zoom/pan capabilities and hover tooltips
- **Modern color schemes** with gradient overlays and particle backgrounds

### � **Advanced Data Visualization**
- **Interactive time-series charts** using Chart.js
- **Historical data analysis** spanning from June 2025 to present
- **Peak flow calculations** with automatic caching
- **Flood level status indicators** with color-coded alerts
- **Date range filtering** with custom time period selection
- **Export capabilities** for data analysis

### 🔄 **Hybrid Data Collection**
- **Primary**: Public FFD endpoints (`ffd.gov.pk/api/dams`, `/api/headworks`)
- **Fallback**: PM Dashboard API endpoint with authentication
- **Remote collector** via GitHub Actions (hourly updates)
- **Local caching** with 10-minute refresh intervals
- **SQLite database** for historical data storage

## 🏗️ Architecture

### **Frontend Stack**
- **HTML5/CSS3/JavaScript** (Vanilla - no build process required)
- **Chart.js** for interactive data visualization
- **Bootstrap 5** for responsive grid system
- **Font Awesome** for iconography
- **Google Fonts** (Inter/Poppins) for typography

### **Backend Stack**
- **Flask** web framework with CORS support
- **SQLite** for local data persistence
- **APScheduler** for automated data collection
- **Requests** for external API integration
- **Python-dotenv** for environment configuration

### **Data Pipeline**
```
FFD APIs → Remote Collector → GitHub Actions → SQLite DB → Flask API → Frontend
```

### **Data Sources**
1. **Primary**: `https://ffd.gov.pk/api/dams` & `/api/headworks`
2. **Fallback**: `https://ffd.pmd.gov.pk/api/pm-dashboard` (requires API key)
3. **Historical**: CSV data (June 15 - August 18, 2025)
4. **Database**: SQLite records from August 19, 2025 onwards

## 🛠️ Installation & Setup

### **Prerequisites**
- Python 3.8+ 
- Modern web browser
- Git (for remote updates)

### **Quick Start**

1. **Clone the repository**
   ```bash
   git clone https://github.com/Ibrahom1/hydrosituation.git
   cd hydrosituation
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv .venv
   ./.venv/Scripts/Activate.ps1  # Windows
   # source .venv/bin/activate    # Linux/Mac
   
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env file with your API key:
   # FFD_API_KEY=your_token_here
   # REMOTE_DATA_URL=https://raw.githubusercontent.com/Ibrahom1/hydrosituation/main/latest.json
   ```

4. **Start the Backend**
   ```bash
   python app.py
   ```

5. **Access the Dashboard**
   ```bash
   # Option 1: Direct file access
   open index.html
   
   # Option 2: Local server (recommended)
   cd ..
   python -m http.server 8080
   # Visit: http://localhost:8080
   ```

## 📡 API Documentation

### **Core Endpoints**

#### **Current Data**
```http
GET /api/ffd-dams           # Current dam data
GET /api/ffd-headworks      # Headworks grouped by river  
GET /api/ffd-telemetries    # Combined telemetry data
```

#### **Historical Data**
```http
GET /api/history?name=Tarbela&days=7          # Last 7 days
GET /api/history?name=Kalabagh&hours=24       # Last 24 hours  
GET /api/history?name=Rasul&start_date=2025-09-01&end_date=2025-09-26
```

#### **System Management**
```http
GET /api/health             # System health check
GET /api/sync-remote        # Sync remote dataset
GET /api/storage-status     # Database status
```

### **Response Format**
```json
{
  "success": true,
  "timestamp": "2025-09-26T10:30:00.000Z",
  "data": {
    "dams": [...],
    "headworks": [...],
    "headworks_by_river": {
      "INDUS": [...],
      "JHELUM": [...]
    }
  }
}
```

## 🎨 UI/UX Features

### **Modern Design Elements**
- **Glassmorphism**: Frosted glass effect with backdrop blur
- **3D Depth**: Multi-layered shadows and transforms
- **Smooth Animations**: 2.5-3 second progressive line drawing
- **Micro-interactions**: Hover effects, button animations, loading states
- **Responsive Layout**: Optimized for desktop, tablet, and mobile

### **Chart Features**
- **Grid-free visualization**: Clean axis-only display
- **Animated line drawing**: Stock-market style progressive rendering
- **Interactive controls**: Zoom, pan, date range selection
- **Peak flow indicators**: Automatic calculation and display
- **Status badges**: Color-coded flood level indicators

## 📁 Project Structure

```
SU Dashboard/
├── 📄 index.html                    # Main dashboard UI
├── 🎨 styles.css                    # Enhanced CSS with 3D effects
├── ⚡ script.js                     # Frontend logic & animations
├── ⚙️ config.js                     # API configuration
├── 🖼️ ndma-logo.png                 # NDMA logo asset
├── 📊 latest.json                   # Remote dataset cache
├── 📈 historic2025flooddata_16june.csv # Historical CSV data
├── 🤖 remote_collector.py           # Data collection script
├── 📋 .env.example                  # Environment template
├── 🗃️ hydro_history.db              # SQLite database
├── 📖 README.md                     # This documentation
├── 🔧 backend/
│   ├── 🐍 app.py                    # Flask application
│   ├── 📦 requirements.txt          # Python dependencies  
│   └── 🧪 test_ffd_api.py           # API testing utilities
├── 🚀 .github/workflows/
│   └── ⏰ remote-collector.yml       # Automated data collection
└── ⚡ .vscode/
    └── ⚙️ settings.json              # VS Code configuration
```

## 🚨 Troubleshooting

### **Common Issues**

#### **Charts Not Displaying**
- Ensure Chart.js libraries are loaded
- Check browser console for JavaScript errors
- Verify API endpoints are responding
- Clear browser cache and refresh

#### **API Connection Errors**
- Verify backend server is running on port 5000
- Check CORS configuration for cross-origin requests
- Ensure environment variables are properly set
- Test API endpoints directly

## 🤝 Contributing

### **Development Setup**
1. Fork the repository
2. Create feature branch: `git checkout -b feature/enhancement-name`
3. Make changes with proper testing
4. Commit with descriptive messages
5. Push and create pull request

### **Code Standards**
- **JavaScript**: ES6+ features, meaningful variable names
- **CSS**: BEM methodology, CSS custom properties
- **Python**: PEP 8 compliance, comprehensive error handling
- **Documentation**: Clear comments and README updates

## 📜 License

This project is licensed under the MIT License.

## 🏆 Acknowledgments

- **National Disaster Management Authority (NDMA)** for institutional support
- **Flood Forecasting Division (FFD)** for providing real-time data APIs  
- **Chart.js Community** for excellent charting library
- **Flask Community** for robust web framework

---

**🇵🇰 Built for Pakistan's Water Resource Management**

*Real-time monitoring • Modern UI • Reliable data collection • Open source*
