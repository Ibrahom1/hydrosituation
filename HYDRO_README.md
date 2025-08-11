# Hydrological Situation Dashboard

## Overview
A focused dashboard displaying real-time hydrological telemetry data from Pakistan's Flood Forecasting Division (FFD). This streamlined application provides essential water level, flow rate, and operational data for dams and headworks across Pakistan.

## Features

### Core Functionality
- **Real-time FFD Telemetry Data**: Direct integration with PMD's FFD API
- **Dam Monitoring**: Display of 3 major dams (Tarbela, Chashma, Mangla)
- **Headworks Tracking**: Monitor 27+ headworks and barrages
- **Visual Trends**: Mini charts showing discharge trends for each location
- **Responsive Design**: Optimized for all screen sizes and devices

### Data Display
- **Water Levels**: Current levels in feet
- **Flow Rates**: Inflow and outflow in cusecs
- **Operational Status**: Normal, Low, Critical indicators
- **Trend Analysis**: Rising, Falling, Steady patterns
- **Location Data**: Geographic coordinates for each site

### Technical Features
- **Auto-refresh**: Data updates every 5 minutes
- **Manual Refresh**: Click refresh button for immediate updates
- **Error Handling**: Graceful handling of API failures
- **Print Support**: Optimized printing for reports
- **Keyboard Shortcuts**: F5 or Ctrl+R for refresh

## File Structure

```
SU Dashboard/
├── index.html          # Main dashboard interface
├── styles.css          # Responsive CSS styling
├── script.js           # Frontend JavaScript with Chart.js
├── ndma-logo.png       # NDMA logo asset
├── backend/
│   ├── app.py          # Flask API server
│   ├── app_old.py      # Previous version backup
│   └── requirements.txt # Python dependencies
└── old_files/          # Previous dashboard backup
```

## Setup Instructions

### Prerequisites
- Python 3.7+
- Modern web browser
- Internet connection for FFD API access

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the Flask server:
   ```bash
   python app.py
   ```

4. Server will start on `http://localhost:5000`

### Frontend Access
1. Open `index.html` in a web browser
2. Or use a local HTTP server for better performance

## API Endpoints

### Backend Endpoints
- `GET /api/health` - Service health check
- `GET /api/ffd-telemetries` - All telemetry data with categorization
- `GET /api/ffd-dams` - Dam-specific data only
- `GET /api/ffd-headworks` - Headworks-specific data only

### Data Source
- **FFD API**: `https://ffd.pmd.gov.pk/api/pm-dashboard`
- **Authentication**: Token-based (PM_PORT_API_1a2b9c6d5e4f)
- **Update Frequency**: Real-time from PMD servers

## Responsive Design

### Screen Compatibility
- **Desktop**: 1920x1080 and larger displays
- **Laptop**: 1366x768 and similar resolutions
- **Tablet**: iPad and Android tablets
- **Mobile**: Smartphones in portrait/landscape

### Layout Features
- **Two-column layout**: Dams and Headworks side-by-side on larger screens
- **Single column**: Stacked layout on mobile devices
- **Scrollable tables**: Handle large datasets efficiently
- **Touch-friendly**: Optimized for touch interactions

## Data Categories

### Dams & Reservoirs
- **Tarbela Dam**: Main reservoir on River Indus
- **Chashma Dam**: Hydroelectric dam on River Indus
- **Mangla Dam**: Major dam on River Jhelum

### Headworks & Barrages
- **River Indus**: Multiple monitoring points from north to south
- **River Jhelum**: Headworks in Kashmir and Punjab regions
- **Tributary Rivers**: Various smaller rivers and canals
- **Cross-border**: Monitoring points near international borders

## Data Fields

### Common Fields
- **Name**: Site identification
- **Location**: Geographic reference
- **Status**: Operational status (Normal, Low, Critical)
- **Recording Time**: Last data update timestamp

### Dam-Specific Fields
- **Inflow**: Water entering the reservoir (cusecs)
- **Outflow**: Water being discharged (cusecs)
- **Storage Percentage**: Reservoir capacity utilization
- **Water Level**: Current water level (feet)

### Headwork-Specific Fields
- **Discharge**: Water flow rate (cusecs)
- **Gate Position**: Operational gate settings
- **Water Level**: Current water level (feet)
- **Trend**: Flow pattern (Rising/Falling/Steady)

## Browser Compatibility
- **Chrome**: 90+
- **Firefox**: 88+
- **Safari**: 14+
- **Edge**: 90+
- **Mobile Browsers**: iOS Safari, Chrome Mobile

## Print Functionality
The dashboard includes print-optimized CSS for generating reports:
- Clean black and white layout
- Removes interactive elements
- Preserves data tables and structure
- Suitable for official documentation

## Performance Features
- **Efficient API calls**: Minimal server requests
- **Client-side caching**: Reduces redundant data fetching
- **Optimized rendering**: Fast table updates
- **Background processing**: Non-blocking data updates

## Security Features
- **CORS enabled**: Secure cross-origin requests
- **Token authentication**: Secure API access
- **Input validation**: Protected against malformed data
- **Error boundaries**: Graceful error handling

## Development Notes

### Previous Version
The original dashboard included:
- Indian dam data
- Weather forecasting
- Map projections
- Admin panels
- Multiple data sources

### Current Focus
Streamlined to essential hydrological data:
- Pakistan FFD telemetries only
- Real-time operational data
- Clean, focused interface
- Optimized performance

### Future Enhancements
Potential improvements:
- Historical data charts
- Alert notifications
- Data export functionality
- Mobile app version

## Troubleshooting

### Common Issues
1. **API Connection**: Ensure internet connectivity and FFD API availability
2. **CORS Errors**: Run backend server on localhost:5000
3. **Data Loading**: Check browser console for JavaScript errors
4. **Display Issues**: Verify CSS file is properly linked

### Debug Mode
Enable Flask debug mode for development:
```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

## Contact Information
- **Organization**: Pakistan Meteorological Department
- **Division**: Flood Forecasting Division
- **Dashboard**: Hydrological Situation Monitoring
- **Last Updated**: August 2025

## License
Government of Pakistan - Public Domain

---

*This dashboard provides critical flood monitoring data for Pakistan's water management and disaster preparedness efforts.*
