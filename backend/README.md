# SU Dashboard Backend

Flask backend server for the Situation Update Dashboard that handles media file uploads and serves them to the frontend.

## Features

### 🚀 **Media Upload System**
- **File Types**: Images (JPG, PNG, GIF), Videos (MP4, WebM, AVI, MOV)
- **File Size**: Up to 50MB per file
- **Security**: Secure filename handling and file type validation
- **Storage**: Local file system with unique filename generation

### 📡 **API Endpoints**
- `POST /api/upload` - Upload media files
- `GET /api/media/<filename>` - Serve uploaded media
- `GET /api/current-media` - Get current displayed media info
- `GET /api/dashboard-data` - Get dashboard data
- `POST /api/dashboard-data` - Save dashboard data
- `GET /api/media-list` - List all uploaded files
- `DELETE /api/delete-media/<filename>` - Delete media files
- `GET /api/health` - Health check

### 🔧 **Configuration**
- **CORS enabled** for frontend integration
- **File size limits** configurable
- **Upload directory** automatically created
- **Error handling** with proper HTTP status codes

## Quick Start

### Windows Setup

1. **Run Setup** (installs Python dependencies):
   ```batch
   cd backend
   setup.bat
   ```

2. **Start Server**:
   ```batch
   start_backend.bat
   ```

The server will start on `http://localhost:5000`

### Manual Setup (All Platforms)

1. **Install Python 3.8+**

2. **Create Virtual Environment**:
   ```bash
   cd backend
   python -m venv venv
   ```

3. **Activate Virtual Environment**:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Start Server**:
   ```bash
   python app.py
   ```

## File Structure

```
backend/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── setup.bat             # Windows setup script
├── start_backend.bat     # Windows start script
├── uploads/              # Upload directory (auto-created)
├── dashboard_data.json   # Dashboard data storage (auto-created)
└── current_media.json    # Current media info (auto-created)
```

## API Usage Examples

### Upload File
```bash
curl -X POST -F "file=@image.jpg" http://localhost:5000/api/upload
```

### Get Current Media
```bash
curl http://localhost:5000/api/current-media
```

### Health Check
```bash
curl http://localhost:5000/api/health
```

## Frontend Integration

The frontend JavaScript automatically connects to the backend:

```javascript
const API_BASE_URL = 'http://localhost:5000/api';
```

Make sure the backend server is running before using the frontend upload functionality.

## Security Features

- **File type validation** - Only allowed extensions
- **Secure filename handling** - Prevents directory traversal
- **File size limits** - Prevents large file uploads
- **CORS configuration** - Controlled cross-origin access
- **Unique filename generation** - Prevents file conflicts

## Deployment Options

### Local Development
- Use the provided batch scripts for Windows
- Or manual setup for other platforms

### Production Deployment
- **Heroku**: Add `Procfile` with `web: python app.py`
- **Railway**: Direct deployment from GitHub
- **DigitalOcean App Platform**: Auto-detected Flask app
- **AWS EC2**: Deploy with Gunicorn
- **Docker**: Create Dockerfile for containerization

### Environment Variables
Create `.env` file for production:
```
FLASK_ENV=production
UPLOAD_FOLDER=uploads
MAX_FILE_SIZE=52428800
```

## Troubleshooting

### Common Issues

1. **Port 5000 already in use**:
   - Change port in `app.py`: `app.run(port=5001)`
   - Update frontend `API_BASE_URL` accordingly

2. **File upload fails**:
   - Check file size (max 50MB)
   - Verify file type is allowed
   - Ensure uploads directory is writable

3. **CORS errors**:
   - Verify Flask-CORS is installed
   - Check browser developer console for details

### Logs
The server provides detailed logging:
- File upload success/failure
- API request information
- Error messages with stack traces

## Performance Notes

- Files are served directly by Flask (suitable for development)
- For production, consider using nginx for static file serving
- File storage is local filesystem (consider cloud storage for scale)
- No file compression implemented (can be added if needed)

## License
This project is open source and available under the MIT License.

---

**Built with 🐍 Flask for reliable media serving**
