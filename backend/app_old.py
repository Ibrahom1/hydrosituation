from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import json
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
import mimetypes
import requests

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'avi', 'mov'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
DATA_FILE = 'dashboard_data.json'
CURRENT_MEDIA_FILE = 'current_media.json'
DASHBOARD_CUSTOM_DATA_FILE = 'custom_dashboard_data.json'

# FFD API Configuration
FFD_TOKEN = "PM_PORT_API_1a2b9c6d5e4f"
FFD_API_URL = "https://ffd.pmd.gov.pk/api/pm-dashboard"

# Dam names mapping for matching with FFD API data
DAM_NAMES_MAPPING = {
    'Tarbela': ['Tarbela', 'TARBELA', 'tarbela'],
    'Mangla': ['Mangla', 'MANGLA', 'mangla'],
    'Chashma': ['Chashma', 'CHASHMA', 'chashma']
}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_current_media(filename, file_type):
    """Save current media info to file"""
    media_info = {
        'filename': filename,
        'file_type': file_type,
        'uploaded_at': datetime.now().isoformat()
    }
    with open(CURRENT_MEDIA_FILE, 'w') as f:
        json.dump(media_info, f)

def get_current_media():
    """Get current media info"""
    try:
        with open(CURRENT_MEDIA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def convert_to_number(value):
    """Converts string with commas to a float or 'n/a' if invalid."""
    if value and value != "n/a":
        try:
            return float(value.replace(",", ""))
        except (ValueError, AttributeError):
            return "n/a"
    return "n/a"

def fetch_ffd_data():
    """Fetch data from FFD API"""
    try:
        response = requests.post(FFD_API_URL, data={"API_KEY": FFD_TOKEN}, timeout=30)
        response.raise_for_status()
        
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return response.json()
        return None
    except requests.RequestException:
        return None

def process_dam_data(ffd_data):
    """Process FFD data and match with dashboard dams"""
    if not ffd_data or 'data' not in ffd_data:
        return {}
    
    dam_data = {}
    locations = ffd_data.get("data", [])
    
    for location in locations:
        location_name = location.get("name", "")
        
        # Try to match with our dam names
        for dam_key, possible_names in DAM_NAMES_MAPPING.items():
            if any(name.lower() in location_name.lower() for name in possible_names):
                dam_data[dam_key] = {
                    'name': location_name,
                    'current_level': convert_to_number(location.get('water_level')),
                    'inflow_discharge': convert_to_number(location.get('inflow_discharge')),
                    'outflow_discharge': convert_to_number(location.get('outflow_discharge')),
                    'recording_time': location.get('recording_time', 'n/a'),
                    'outflow_time': location.get('outflow_time', 'n/a'),
                    'status': location.get('status', 'n/a'),
                    'inflow_trend': location.get('inflow_trend', 'n/a'),
                    'outflow_trend': location.get('outflow_trend', 'n/a')
                }
                break
    
    return dam_data

def calculate_percentage_filled(current_level, max_level):
    """Calculate percentage filled for dams"""
    try:
        if current_level != "n/a" and max_level > 0:
            return round((float(current_level) / max_level) * 100, 1)
        return "n/a"
    except (ValueError, TypeError):
        return "n/a"

def get_badge_class(percentage):
    """Get Bootstrap badge class based on percentage"""
    if percentage == "n/a":
        return "bg-secondary"
    
    try:
        perc = float(percentage)
        if perc >= 80:
            return "bg-success"
        elif perc >= 60:
            return "bg-warning"
        else:
            return "bg-danger"
    except (ValueError, TypeError):
        return "bg-secondary"

def save_custom_dashboard_data(data):
    """Save custom dashboard data to file with merging"""
    try:
        # Load existing data first
        existing_data = get_custom_dashboard_data()
        
        # Merge new data with existing data
        if existing_data:
            # Merge pakistan_dams
            if 'pakistan_dams' in data:
                if 'pakistan_dams' not in existing_data:
                    existing_data['pakistan_dams'] = {}
                existing_data['pakistan_dams'].update(data['pakistan_dams'])
            
            # Merge indian_dams
            if 'indian_dams' in data:
                if 'indian_dams' not in existing_data:
                    existing_data['indian_dams'] = {}
                existing_data['indian_dams'].update(data['indian_dams'])
            
            # Merge weather_forecast
            if 'weather_forecast' in data:
                if 'weather_forecast' not in existing_data:
                    existing_data['weather_forecast'] = {}
                existing_data['weather_forecast'].update(data['weather_forecast'])
            
            # Use merged data
            merged_data = existing_data
        else:
            # No existing data, use new data
            merged_data = data
        
        # Update timestamp
        merged_data['last_updated'] = datetime.now().isoformat()
        
        # Save merged data
        with open(DASHBOARD_CUSTOM_DATA_FILE, 'w') as f:
            json.dump(merged_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving custom dashboard data: {e}")
        return False

def get_custom_dashboard_data():
    """Get custom dashboard data from file"""
    try:
        with open(DASHBOARD_CUSTOM_DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default structure if file doesn't exist
        return {
            'pakistan_dams': {
                'Tarbela': {'current_level': '', 'fill_percentage': ''},
                'Mangla': {'current_level': '', 'fill_percentage': ''},
                'Chashma': {'current_level': '', 'fill_percentage': ''}
            },
            'indian_dams': {
                'Pong': {'current_level': '', 'fill_percentage': ''},
                'Bhakra': {'current_level': '', 'fill_percentage': ''},
                'Thein': {'current_level': '', 'fill_percentage': ''}
            },
            'weather_forecast': {
                'AJ&K': '',
                'Islamabad': '',
                'GB': '',
                'KP': '',
                'Punjab': '',
                'Sindh': '',
                'Balochistan': ''
            },
            'last_updated': None
        }
    except Exception as e:
        print(f"Error loading custom dashboard data: {e}")
        return None

@app.route('/')
def home():
    """Root endpoint with API information"""
    return jsonify({
        'message': 'SU Dashboard Backend API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            'upload': 'POST /api/upload',
            'get_media': 'GET /api/media/<filename>',
            'current_media': 'GET /api/current-media',
            'ffd_dam_data': 'GET /api/ffd-dam-data',
            'custom_dashboard_data': 'GET/POST /api/custom-dashboard-data',
            'media_list': 'GET /api/media-list',
            'delete_media': 'DELETE /api/delete-media/<filename>',
            'test_upload': 'GET /test-upload',
            'health': 'GET /api/health'
        },
        'upload_folder': os.path.abspath(app.config['UPLOAD_FOLDER']),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/ffd-dam-data')
def get_ffd_dam_data():
    """Get dam data from FFD API"""
    try:
        # Fetch data from FFD API
        ffd_data = fetch_ffd_data()
        
        if not ffd_data:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch data from FFD API',
                'dams': {}
            }), 500
        
        # Process the data
        dam_data = process_dam_data(ffd_data)
        
        # Add static max levels and calculate percentages
        static_max_levels = {
            'Tarbela': 1550,
            'Mangla': 1242,
            'Chashma': 649
        }
        
        enhanced_dam_data = {}
        for dam_name, data in dam_data.items():
            max_level = static_max_levels.get(dam_name, 0)
            current_level = data.get('current_level', 'n/a')
            percentage = calculate_percentage_filled(current_level, max_level)
            
            enhanced_dam_data[dam_name] = {
                **data,
                'max_conservation_level': max_level,
                'percentage_filled': percentage,
                'badge_class': get_badge_class(percentage)
            }
        
        return jsonify({
            'success': True,
            'dams': enhanced_dam_data,
            'fetched_at': datetime.now().isoformat(),
            'source': 'FFD API'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}',
            'dams': {}
        }), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Enhanced file upload endpoint with better validation and response"""
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided',
                'message': 'Please select a file to upload'
            }), 400
        
        file = request.files['file']
        
        # Check if file was selected
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected',
                'message': 'Please choose a file before uploading'
            }), 400
        
        # Validate file type
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'File type not allowed',
                'message': f'Allowed types: {", ".join(ALLOWED_EXTENSIONS)}',
                'allowed_extensions': list(ALLOWED_EXTENSIONS)
            }), 400
        
        # Check file size (additional check beyond Flask's MAX_CONTENT_LENGTH)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'error': 'File too large',
                'message': f'Maximum file size is {MAX_FILE_SIZE // (1024*1024)}MB',
                'file_size': file_size,
                'max_size': MAX_FILE_SIZE
            }), 413
        
        # Generate secure filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        # Ensure upload directory exists
        uploads_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(uploads_dir, unique_filename)
        file.save(file_path)
        
        # Verify file was saved
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': 'File save failed',
                'message': 'File could not be saved to server'
            }), 500
        
        # Get file type and metadata
        file_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        file_stats = os.stat(file_path)
        
        # Save as current media
        save_current_media(unique_filename, file_type)
        
        # Success response
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully and set as current dashboard media',
            'data': {
                'filename': unique_filename,
                'original_filename': original_filename,
                'file_type': file_type,
                'file_size': file_stats.st_size,
                'file_size_mb': round(file_stats.st_size / (1024*1024), 2),
                'media_url': f'/api/media/{unique_filename}',
                'uploaded_at': datetime.now().isoformat()
            }
        }), 200
        
    except Exception as e:
        # Log error for debugging
        print(f"Upload error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Server error',
            'message': 'An unexpected error occurred during upload',
            'details': str(e) if app.debug else None
        }), 500

@app.route('/api/media/<filename>')
def get_media(filename):
    """Serve uploaded media files"""
    try:
        # Get absolute path to the uploads directory
        uploads_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
        file_path = os.path.join(uploads_dir, filename)
        
        print(f"Looking for file at: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        
        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            print(f"File not found: {file_path}")
            print(f"Files in upload dir: {os.listdir(uploads_dir) if os.path.exists(uploads_dir) else 'Directory does not exist'}")
            return jsonify({'error': f'File not found: {filename}'}), 404
    except Exception as e:
        print(f"Error serving media file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/current-media')
def current_media():
    """Get current media information"""
    try:
        media_info = get_current_media()
        if media_info:
            # Check if file still exists
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], media_info['filename'])
            if os.path.exists(file_path):
                return jsonify(media_info), 200
        
        return jsonify({'filename': None}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/custom-dashboard-data', methods=['GET', 'POST'])
def custom_dashboard_data():
    """Handle custom dashboard data operations"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            if save_custom_dashboard_data(data):
                return jsonify({
                    'success': True,
                    'message': 'Dashboard data saved successfully',
                    'data': data
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to save dashboard data'
                }), 500
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500
    
    else:  # GET request
        try:
            data = get_custom_dashboard_data()
            if data is not None:
                return jsonify({
                    'success': True,
                    'data': data
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to load dashboard data'
                }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500



@app.route('/api/delete-media/<filename>', methods=['DELETE'])
def delete_media(filename):
    """Delete uploaded media file"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Clear current media if it's the deleted file
            current = get_current_media()
            if current and current['filename'] == filename:
                if os.path.exists(CURRENT_MEDIA_FILE):
                    os.remove(CURRENT_MEDIA_FILE)
            
            return jsonify({'message': 'File deleted successfully'}), 200
        else:
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/media-list')
def media_list():
    """Get list of all uploaded media files"""
    try:
        files = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                file_stats = os.stat(file_path)
                file_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
                
                files.append({
                    'filename': filename,
                    'file_type': file_type,
                    'size': file_stats.st_size,
                    'created_at': datetime.fromtimestamp(file_stats.st_ctime).isoformat()
                })
        
        return jsonify({'files': files}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    }), 200

@app.route('/api/debug-data')
def debug_data():
    """Debug endpoint to check current data"""
    try:
        custom_data = get_custom_dashboard_data()
        return jsonify({
            'custom_data': custom_data,
            'files_exist': {
                'custom_data_file': os.path.exists(DASHBOARD_CUSTOM_DATA_FILE),
                'current_media_file': os.path.exists(CURRENT_MEDIA_FILE)
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-dam-data', methods=['POST'])
def test_dam_data():
    """Test endpoint to add sample dam data"""
    try:
        sample_data = {
            'pakistan_dams': {
                'Tarbela': {'current_level': '1545'},
                'Mangla': {'current_level': '1203.75'},
                'Chashma': {'current_level': '641'}
            },
            'indian_dams': {
                'Pong': {'current_level': '1355.15'},
                'Bhakra': {'current_level': '1621.60'},
                'Thein': {'current_level': '1672.06'}
            }
        }
        
        if save_custom_dashboard_data(sample_data):
            return jsonify({'success': True, 'message': 'Sample dam data added', 'data': sample_data}), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to save data'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/test-upload')
def test_upload_form():
    """Enhanced admin interface for upload and dashboard data management"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SU Dashboard - Admin Panel</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            body { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .admin-container {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                backdrop-filter: blur(10px);
                margin-top: 30px;
                margin-bottom: 30px;
            }
            .upload-area {
                border: 3px dashed #6c757d;
                border-radius: 10px;
                padding: 30px;
                text-align: center;
                transition: all 0.3s ease;
                background: #f8f9fa;
            }
            .upload-area:hover {
                border-color: #0d6efd;
                background: #e3f2fd;
            }
            .upload-area.dragover {
                border-color: #0d6efd;
                background: #e3f2fd;
                transform: scale(1.02);
            }
            .preview-container {
                margin-top: 15px;
                border-radius: 10px;
                overflow: hidden;
            }
            .preview-container img, .preview-container video {
                max-width: 100%;
                height: auto;
                border-radius: 10px;
            }
            .btn-admin {
                background: linear-gradient(45deg, #667eea, #764ba2);
                border: none;
                padding: 10px 25px;
                border-radius: 20px;
                color: white;
                font-weight: 600;
                transition: all 0.3s ease;
                margin: 5px;
            }
            .btn-admin:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(0,0,0,0.2);
                color: white;
            }
            .status-message {
                border-radius: 10px;
                padding: 15px;
                margin: 15px 0;
            }
            .header-title {
                background: linear-gradient(45deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-weight: 700;
            }
            .section-card {
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                margin-bottom: 20px;
                overflow: hidden;
            }
            .section-header {
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                padding: 15px 20px;
                font-weight: 600;
            }
            .table-input {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                width: 100%;
            }
            .table-input:focus {
                border-color: #667eea;
                box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
                outline: none;
            }
            .percentage-badge {
                padding: 6px 12px;
                border-radius: 15px;
                font-weight: 600;
                font-size: 12px;
            }
            .nav-tabs .nav-link {
                border: none;
                border-radius: 10px 10px 0 0;
                margin-right: 5px;
                background: #f8f9fa;
                color: #6c757d;
                font-weight: 600;
            }
            .nav-tabs .nav-link.active {
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
            }
            .tab-content {
                background: white;
                border-radius: 0 10px 10px 10px;
                padding: 25px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="admin-container p-4">
                <h1 class="text-center header-title mb-4">
                    🎛️ SU Dashboard Admin Panel
                </h1>
                
                <!-- Navigation Tabs -->
                <ul class="nav nav-tabs" id="adminTabs" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="media-tab" data-bs-toggle="tab" data-bs-target="#media" type="button" role="tab">
                            <i class="fas fa-photo-video me-2"></i>Media Upload
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="pakistan-tab" data-bs-toggle="tab" data-bs-target="#pakistan" type="button" role="tab">
                            <i class="fas fa-water me-2"></i>Pakistan Dams
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="indian-tab" data-bs-toggle="tab" data-bs-target="#indian" type="button" role="tab">
                            <i class="fas fa-tint me-2"></i>Indian Dams
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="weather-tab" data-bs-toggle="tab" data-bs-target="#weather" type="button" role="tab">
                            <i class="fas fa-cloud-sun me-2"></i>Weather Forecast
                        </button>
                    </li>
                </ul>
                
                <!-- Tab Content -->
                <div class="tab-content" id="adminTabContent">
                    <!-- Media Upload Tab -->
                    <div class="tab-pane fade show active" id="media" role="tabpanel">
                        <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
                            <div class="mb-3">
                                <i class="fas fa-cloud-upload" style="font-size: 3rem; color: #6c757d;"></i>
                            </div>
                            <h5>Click to select or drag & drop files here</h5>
                            <p class="text-muted mb-3">Supports: Images (PNG, JPG, GIF) and Videos (MP4, WebM, AVI, MOV)</p>
                            <p class="text-muted small">Maximum file size: 50MB</p>
                            <input type="file" id="fileInput" accept="image/*,video/*" style="display: none;" />
                        </div>
                        
                        <div class="text-center mt-3">
                            <button class="btn btn-admin" onclick="uploadFile()">
                                <i class="fas fa-upload"></i> Upload Media
                            </button>
                        </div>
                        
                        <div id="mediaStatus" class="status-message" style="display: none;"></div>
                        <div id="mediaPreview" class="preview-container"></div>
                        
                        <hr class="my-4">
                        
                        <div class="text-center">
                            <h5>Current Dashboard Media</h5>
                            <button class="btn btn-outline-primary" onclick="loadCurrentMedia()">
                                <i class="fas fa-refresh"></i> Load Current Media
                            </button>
                        </div>
                        
                        <div id="currentMedia" class="preview-container"></div>
                    </div>
                    
                    <!-- Pakistan Dams Tab -->
                    <div class="tab-pane fade" id="pakistan" role="tabpanel">
                        <h4><i class="fas fa-water me-2 text-primary"></i>Pakistan Dams Data</h4>
                        <p class="text-muted">Update current levels and fill percentages for Pakistan dams (Inflow/Outflow data comes from FFD API automatically)</p>
                        
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead class="table-dark">
                                    <tr>
                                        <th>Dam/Barrage</th>
                                        <th>Max Level (ft)</th>
                                        <th>Current Level (ft)</th>
                                        <th>Fill Percentage (%)</th>
                                        <th>Data Source</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td class="fw-bold">Tarbela</td>
                                        <td class="fw-bold">1550</td>
                                        <td><input type="number" class="table-input" id="tarbela_level" placeholder="Enter current level" step="0.01"></td>
                                        <td><input type="number" class="table-input" id="tarbela_percentage_input" placeholder="Enter percentage" min="0" max="100" step="0.1"></td>
                                        <td><small class="text-muted">Manual + FFD API</small></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">Mangla</td>
                                        <td class="fw-bold">1242</td>
                                        <td><input type="number" class="table-input" id="mangla_level" placeholder="Enter current level" step="0.01"></td>
                                        <td><input type="number" class="table-input" id="mangla_percentage_input" placeholder="Enter percentage" min="0" max="100" step="0.1"></td>
                                        <td><small class="text-muted">Manual + FFD API</small></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">Chashma</td>
                                        <td class="fw-bold">649</td>
                                        <td><input type="number" class="table-input" id="chashma_level" placeholder="Enter current level" step="0.01"></td>
                                        <td><input type="number" class="table-input" id="chashma_percentage_input" placeholder="Enter percentage" min="0" max="100" step="0.1"></td>
                                        <td><small class="text-muted">Manual + FFD API</small></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            <strong>Note:</strong> You can either enter current levels (auto-calculates percentage) OR manually enter the fill percentage. Inflow and Outflow data is automatically fetched from the FFD API every 5 minutes.
                        </div>
                        
                        <div class="text-center mt-3">
                            <button class="btn btn-admin" onclick="savePakistanDamsData()">
                                <i class="fas fa-save"></i> Save Pakistan Dams Data
                            </button>
                        </div>
                        
                        <div id="pakistanStatus" class="status-message" style="display: none;"></div>
                    </div>
                    
                    <!-- Indian Dams Tab -->
                    <div class="tab-pane fade" id="indian" role="tabpanel">
                        <h4><i class="fas fa-tint me-2 text-info"></i>Indian Dams Data</h4>
                        <p class="text-muted">Update current levels and fill percentages for Indian dams</p>
                        
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead class="table-dark">
                                    <tr>
                                        <th>Dam</th>
                                        <th>Max Reservoir Level (ft)</th>
                                        <th>Current Level (ft)</th>
                                        <th>Fill Percentage (%)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td class="fw-bold">Pong</td>
                                        <td class="fw-bold">1390</td>
                                        <td><input type="number" class="table-input" id="pong_level" placeholder="Enter current level" step="0.01"></td>
                                        <td><input type="number" class="table-input" id="pong_percentage_input" placeholder="Enter percentage" min="0" max="100" step="0.1"></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">Bhakra</td>
                                        <td class="fw-bold">1680</td>
                                        <td><input type="number" class="table-input" id="bhakra_level" placeholder="Enter current level" step="0.01"></td>
                                        <td><input type="number" class="table-input" id="bhakra_percentage_input" placeholder="Enter percentage" min="0" max="100" step="0.1"></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">Thein</td>
                                        <td class="fw-bold">1732</td>
                                        <td><input type="number" class="table-input" id="thein_level" placeholder="Enter current level" step="0.01"></td>
                                        <td><input type="number" class="table-input" id="thein_percentage_input" placeholder="Enter percentage" min="0" max="100" step="0.1"></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            <strong>Note:</strong> You can either enter current levels (auto-calculates percentage) OR manually enter the fill percentage.
                        </div>
                        
                        <div class="text-center mt-3">
                            <button class="btn btn-admin" onclick="saveIndianDamsData()">
                                <i class="fas fa-save"></i> Save Indian Dams Data
                            </button>
                        </div>
                        
                        <div id="indianStatus" class="status-message" style="display: none;"></div>
                    </div>
                    
                    <!-- Weather Forecast Tab -->
                    <div class="tab-pane fade" id="weather" role="tabpanel">
                        <h4><i class="fas fa-cloud-sun me-2 text-warning"></i>Weather Forecast</h4>
                        <p class="text-muted">Update weather forecast for each province (Next 12 Hours)</p>
                        
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead class="table-dark">
                                    <tr>
                                        <th style="width: 20%;">Province</th>
                                        <th style="width: 80%;">Forecast</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td class="fw-bold">AJ&K</td>
                                        <td><textarea class="table-input" id="ajk_forecast" rows="2" placeholder="Enter weather forecast for AJ&K"></textarea></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">Islamabad</td>
                                        <td><textarea class="table-input" id="islamabad_forecast" rows="2" placeholder="Enter weather forecast for Islamabad"></textarea></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">GB</td>
                                        <td><textarea class="table-input" id="gb_forecast" rows="2" placeholder="Enter weather forecast for GB"></textarea></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">KP</td>
                                        <td><textarea class="table-input" id="kp_forecast" rows="2" placeholder="Enter weather forecast for KP"></textarea></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">Punjab</td>
                                        <td><textarea class="table-input" id="punjab_forecast" rows="2" placeholder="Enter weather forecast for Punjab"></textarea></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">Sindh</td>
                                        <td><textarea class="table-input" id="sindh_forecast" rows="2" placeholder="Enter weather forecast for Sindh"></textarea></td>
                                    </tr>
                                    <tr>
                                        <td class="fw-bold">Balochistan</td>
                                        <td><textarea class="table-input" id="balochistan_forecast" rows="2" placeholder="Enter weather forecast for Balochistan"></textarea></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        
                        <div class="text-center mt-3">
                            <button class="btn btn-admin" onclick="saveWeatherForecast()">
                                <i class="fas fa-save"></i> Save Weather Forecast
                            </button>
                        </div>
                        
                        <div id="weatherStatus" class="status-message" style="display: none;"></div>
                    </div>
                </div>
                
                <!-- Global Actions -->
                <hr class="my-4">
                <div class="text-center">
                    <button class="btn btn-admin" onclick="loadAllData()">
                        <i class="fas fa-download"></i> Load All Data
                    </button>
                    <button class="btn btn-admin" onclick="saveAllData()">
                        <i class="fas fa-save"></i> Save All Data
                    </button>
                    <button class="btn btn-outline-success" onclick="window.open('/', '_blank')">
                        <i class="fas fa-external-link-alt"></i> View Dashboard
                    </button>
                </div>
                
                <div id="globalStatus" class="status-message" style="display: none;"></div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            const API_BASE = window.location.origin + '/api';
            
            // Dam max levels for percentage calculations
            const DAM_MAX_LEVELS = {
                'tarbela': 1550,
                'mangla': 1242,
                'chashma': 649,
                'pong': 1390,
                'bhakra': 1680,
                'thein': 1732
            };
            
            // Auto-calculate percentages when levels change
            document.addEventListener('input', function(e) {
                if (e.target.id.includes('_level')) {
                    const damName = e.target.id.split('_')[0];
                    calculatePercentage(damName, e.target.value);
                }
            });
            
            function calculatePercentage(damName, currentLevel) {
                const maxLevel = DAM_MAX_LEVELS[damName];
                const percentageElement = document.getElementById(damName + '_percentage');
                
                if (maxLevel && currentLevel && percentageElement) {
                    const percentage = Math.round((parseFloat(currentLevel) / maxLevel) * 100);
                    percentageElement.textContent = percentage + '%';
                    
                    // Update badge color
                    percentageElement.className = 'percentage-badge ';
                    if (percentage >= 80) {
                        percentageElement.className += 'bg-success';
                    } else if (percentage >= 60) {
                        percentageElement.className += 'bg-warning';
                    } else if (percentage >= 40) {
                        percentageElement.className += 'bg-info';
                    } else {
                        percentageElement.className += 'bg-danger';
                    }
                } else if (percentageElement) {
                    percentageElement.textContent = '--%';
                    percentageElement.className = 'percentage-badge bg-secondary';
                }
            }
            
            // Media Upload Functions
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    previewFile(files[0]);
                }
            });
            
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    previewFile(e.target.files[0]);
                }
            });
            
            function previewFile(file) {
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    const preview = document.getElementById('mediaPreview');
                    let previewHTML = '';
                    
                    if (file.type.startsWith('image/')) {
                        previewHTML = `
                            <div class="text-center">
                                <h6 class="mb-3">Preview:</h6>
                                <img src="${e.target.result}" alt="Preview" class="img-fluid" style="max-height: 300px;">
                                <p class="mt-2 text-muted">${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)</p>
                            </div>
                        `;
                    } else if (file.type.startsWith('video/')) {
                        previewHTML = `
                            <div class="text-center">
                                <h6 class="mb-3">Preview:</h6>
                                <video controls class="img-fluid" style="max-height: 300px;">
                                    <source src="${e.target.result}" type="${file.type}">
                                </video>
                                <p class="mt-2 text-muted">${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)</p>
                            </div>
                        `;
                    }
                    
                    preview.innerHTML = previewHTML;
                };
                
                reader.readAsDataURL(file);
            }
            
            async function uploadFile() {
                const fileInput = document.getElementById('fileInput');
                const file = fileInput.files[0];
                
                if (!file) {
                    showStatus('mediaStatus', 'Please select a file first!', 'danger');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', file);
                
                showStatus('mediaStatus', 'Uploading... Please wait.', 'info');
                
                try {
                    const response = await fetch(API_BASE + '/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok && result.success) {
                        showStatus('mediaStatus', '✅ Upload successful! Media is now live on the dashboard.', 'success');
                        displayMedia(result.data.filename, result.data.file_type, 'currentMedia');
                    } else {
                        showStatus('mediaStatus', '❌ Upload failed: ' + result.error, 'danger');
                    }
                } catch (error) {
                    showStatus('mediaStatus', '❌ Network error: ' + error.message, 'danger');
                }
            }
            
            function displayMedia(filename, fileType, containerId) {
                const mediaURL = API_BASE + '/media/' + filename;
                let mediaHTML = '';
                
                if (fileType.startsWith('image/')) {
                    mediaHTML = `
                        <div class="text-center mt-3">
                            <h6>Current Media:</h6>
                            <img src="${mediaURL}" alt="Current media" class="img-fluid" style="max-height: 300px;">
                            <p class="mt-2 text-muted small">${filename}</p>
                        </div>
                    `;
                } else if (fileType.startsWith('video/')) {
                    mediaHTML = `
                        <div class="text-center mt-3">
                            <h6>Current Media:</h6>
                            <video controls class="img-fluid" style="max-height: 300px;">
                                <source src="${mediaURL}" type="${fileType}">
                            </video>
                            <p class="mt-2 text-muted small">${filename}</p>
                        </div>
                    `;
                }
                
                document.getElementById(containerId).innerHTML = mediaHTML;
            }
            
            async function loadCurrentMedia() {
                try {
                    const response = await fetch(API_BASE + '/current-media');
                    const result = await response.json();
                    
                    if (result.filename) {
                        displayMedia(result.filename, result.file_type, 'currentMedia');
                        showStatus('mediaStatus', 'Current media loaded successfully.', 'info');
                    } else {
                        document.getElementById('currentMedia').innerHTML = `
                            <div class="text-center mt-3">
                                <p class="text-muted">No media currently uploaded to the dashboard.</p>
                            </div>
                        `;
                    }
                } catch (error) {
                    showStatus('mediaStatus', 'Error loading current media: ' + error.message, 'danger');
                }
            }
            
            // Pakistan Dams Functions
            async function savePakistanDamsData() {
                const data = {
                    pakistan_dams: {
                        Tarbela: {
                            current_level: document.getElementById('tarbela_level').value,
                            fill_percentage: document.getElementById('tarbela_percentage_input').value
                        },
                        Mangla: {
                            current_level: document.getElementById('mangla_level').value,
                            fill_percentage: document.getElementById('mangla_percentage_input').value
                        },
                        Chashma: {
                            current_level: document.getElementById('chashma_level').value,
                            fill_percentage: document.getElementById('chashma_percentage_input').value
                        }
                    }
                };
                
                await saveCustomData(data, 'pakistanStatus', 'Pakistan dams data');
            }
            
            // Indian Dams Functions
            async function saveIndianDamsData() {
                const data = {
                    indian_dams: {
                        Pong: {
                            current_level: document.getElementById('pong_level').value,
                            fill_percentage: document.getElementById('pong_percentage_input').value
                        },
                        Bhakra: {
                            current_level: document.getElementById('bhakra_level').value,
                            fill_percentage: document.getElementById('bhakra_percentage_input').value
                        },
                        Thein: {
                            current_level: document.getElementById('thein_level').value,
                            fill_percentage: document.getElementById('thein_percentage_input').value
                        }
                    }
                };
                
                await saveCustomData(data, 'indianStatus', 'Indian dams data');
            }
            
            // Weather Forecast Functions
            async function saveWeatherForecast() {
                const data = {
                    weather_forecast: {
                        'AJ&K': document.getElementById('ajk_forecast').value,
                        'Islamabad': document.getElementById('islamabad_forecast').value,
                        'GB': document.getElementById('gb_forecast').value,
                        'KP': document.getElementById('kp_forecast').value,
                        'Punjab': document.getElementById('punjab_forecast').value,
                        'Sindh': document.getElementById('sindh_forecast').value,
                        'Balochistan': document.getElementById('balochistan_forecast').value
                    }
                };
                
                await saveCustomData(data, 'weatherStatus', 'Weather forecast');
            }
            
            // Generic save function
            async function saveCustomData(data, statusElementId, dataType) {
                showStatus(statusElementId, `Saving ${dataType}...`, 'info');
                
                try {
                    const response = await fetch(API_BASE + '/custom-dashboard-data', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(data)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok && result.success) {
                        showStatus(statusElementId, `✅ ${dataType} saved successfully!`, 'success');
                    } else {
                        showStatus(statusElementId, `❌ Failed to save ${dataType}: ${result.error}`, 'danger');
                    }
                } catch (error) {
                    showStatus(statusElementId, `❌ Network error: ${error.message}`, 'danger');
                }
            }
            
            // Load all data
            async function loadAllData() {
                showStatus('globalStatus', 'Loading all data...', 'info');
                
                try {
                    const response = await fetch(API_BASE + '/custom-dashboard-data');
                    const result = await response.json();
                    
                    if (response.ok && result.success) {
                        const data = result.data;
                        
                        // Load Pakistan dams
                        if (data.pakistan_dams) {
                            Object.keys(data.pakistan_dams).forEach(damName => {
                                const damKey = damName.toLowerCase();
                                const damData = data.pakistan_dams[damName];
                                
                                if (document.getElementById(damKey + '_level')) {
                                    document.getElementById(damKey + '_level').value = damData.current_level || '';
                                }
                                if (document.getElementById(damKey + '_percentage_input')) {
                                    document.getElementById(damKey + '_percentage_input').value = damData.fill_percentage || '';
                                }
                                
                                // Calculate percentage if level is provided but percentage is not
                                if (damData.current_level && !damData.fill_percentage) {
                                    calculatePercentage(damKey, damData.current_level);
                                }
                            });
                        }
                        
                        // Load Indian dams
                        if (data.indian_dams) {
                            Object.keys(data.indian_dams).forEach(damName => {
                                const damKey = damName.toLowerCase();
                                const damData = data.indian_dams[damName];
                                
                                if (document.getElementById(damKey + '_level')) {
                                    document.getElementById(damKey + '_level').value = damData.current_level || '';
                                }
                                if (document.getElementById(damKey + '_percentage_input')) {
                                    document.getElementById(damKey + '_percentage_input').value = damData.fill_percentage || '';
                                }
                                
                                // Calculate percentage if level is provided but percentage is not
                                if (damData.current_level && !damData.fill_percentage) {
                                    calculatePercentage(damKey, damData.current_level);
                                }
                            });
                        }
                        
                        // Load weather forecast
                        if (data.weather_forecast) {
                            Object.keys(data.weather_forecast).forEach(province => {
                                const provinceKey = province.toLowerCase().replace('&', '');
                                const forecastText = data.weather_forecast[province];
                                
                                if (document.getElementById(provinceKey + '_forecast')) {
                                    document.getElementById(provinceKey + '_forecast').value = forecastText || '';
                                }
                            });
                        }
                        
                        showStatus('globalStatus', '✅ All data loaded successfully!', 'success');
                    } else {
                        showStatus('globalStatus', '❌ Failed to load data: ' + result.error, 'danger');
                    }
                } catch (error) {
                    showStatus('globalStatus', '❌ Network error: ' + error.message, 'danger');
                }
            }
            
            // Save all data
            async function saveAllData() {
                const allData = {
                    pakistan_dams: {
                        Tarbela: {
                            current_level: document.getElementById('tarbela_level').value,
                            fill_percentage: document.getElementById('tarbela_percentage_input').value
                        },
                        Mangla: {
                            current_level: document.getElementById('mangla_level').value,
                            fill_percentage: document.getElementById('mangla_percentage_input').value
                        },
                        Chashma: {
                            current_level: document.getElementById('chashma_level').value,
                            fill_percentage: document.getElementById('chashma_percentage_input').value
                        }
                    },
                    indian_dams: {
                        Pong: {
                            current_level: document.getElementById('pong_level').value,
                            fill_percentage: document.getElementById('pong_percentage_input').value
                        },
                        Bhakra: {
                            current_level: document.getElementById('bhakra_level').value,
                            fill_percentage: document.getElementById('bhakra_percentage_input').value
                        },
                        Thein: {
                            current_level: document.getElementById('thein_level').value,
                            fill_percentage: document.getElementById('thein_percentage_input').value
                        }
                    },
                    weather_forecast: {
                        'AJ&K': document.getElementById('ajk_forecast').value,
                        'Islamabad': document.getElementById('islamabad_forecast').value,
                        'GB': document.getElementById('gb_forecast').value,
                        'KP': document.getElementById('kp_forecast').value,
                        'Punjab': document.getElementById('punjab_forecast').value,
                        'Sindh': document.getElementById('sindh_forecast').value,
                        'Balochistan': document.getElementById('balochistan_forecast').value
                    }
                };
                
                await saveCustomData(allData, 'globalStatus', 'All dashboard data');
            }
            
            function showStatus(elementId, message, type) {
                const statusDiv = document.getElementById(elementId);
                statusDiv.className = `status-message alert alert-${type}`;
                statusDiv.innerHTML = message;
                statusDiv.style.display = 'block';
                
                // Auto-hide success messages after 5 seconds
                if (type === 'success') {
                    setTimeout(() => {
                        statusDiv.style.display = 'none';
                    }, 5000);
                }
            }
            
            // Load data and current media on page load
            window.addEventListener('load', function() {
                loadCurrentMedia();
                loadAllData();
            });
        </script>
    </body>
    </html>
    '''

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 50MB.'}), 413

if __name__ == '__main__':
    print("🚀 Starting SU Dashboard Backend Server...")
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"📝 Current media file: {os.path.abspath(CURRENT_MEDIA_FILE)}")
    print("🌐 Access the API at: http://localhost:5000")
    print("� Test Upload Form: http://localhost:5000/test-upload")
    print("�📖 API Documentation:")
    print("   POST /api/upload - Upload media file")
    print("   GET  /api/media/<filename> - Get media file")
    print("   GET  /api/current-media - Get current media info")
    print("   GET  /api/ffd-dam-data - Get FFD dam data")
    print("   GET  /api/media-list - List all media files")
    print("   DELETE /api/delete-media/<filename> - Delete media file")
    print("   GET  /api/health - Health check")
    print("   GET  /test-upload - Upload test form")
    print("\n✨ Ready to serve your dashboard!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
