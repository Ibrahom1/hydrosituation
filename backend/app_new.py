from flask import Flask, jsonify
from flask_cors import CORS
import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)

# FFD API Configuration
FFD_TOKEN = "PM_PORT_API_1a2b9c6d5e4f"
FFD_API_URL = "https://ffd.pmd.gov.pk/api/pm-dashboard"

@app.route('/')
def index():
    return "Hydrological Situation Dashboard API - FFD Telemetries Only"

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'FFD Hydrological Dashboard'
    })

@app.route('/api/ffd-telemetries')
def get_ffd_telemetries():
    """Get all FFD telemetries including dams and headworks"""
    try:
        logging.info("Fetching FFD telemetries...")
        
        # Prepare request data
        request_data = {"API_KEY": FFD_TOKEN}
        
        # Make the API request
        response = requests.post(FFD_API_URL, data=request_data, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'data' in data and isinstance(data['data'], list):
                telemetries = data['data']
                
                # Separate dams and headworks
                dams = []
                headworks = []
                
                for item in telemetries:
                    item_type = item.get('type', '').lower()
                    name = item.get('name', '')
                    
                    # Categorize based on type or name patterns
                    if 'dam' in item_type or 'reservoir' in item_type or any(dam_keyword in name.lower() for dam_keyword in ['dam', 'reservoir', 'tarbela', 'mangla', 'chashma']):
                        dams.append(item)
                    elif 'headwork' in item_type or 'barrage' in item_type or any(hw_keyword in name.lower() for hw_keyword in ['headwork', 'barrage', 'weir']):
                        headworks.append(item)
                    else:
                        # Default categorization based on available data
                        if item.get('reservoir_level') or item.get('storage'):
                            dams.append(item)
                        else:
                            headworks.append(item)
                
                return jsonify({
                    'success': True,
                    'timestamp': datetime.now().isoformat(),
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'total_count': len(telemetries),
                    'dams_count': len(dams),
                    'headworks_count': len(headworks),
                    'dams': dams,
                    'headworks': headworks,
                    'all_telemetries': telemetries
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid data structure from FFD API',
                    'timestamp': datetime.now().isoformat()
                }), 500
                
        else:
            logging.error(f"FFD API request failed with status: {response.status_code}")
            return jsonify({
                'success': False,
                'error': f'FFD API request failed: {response.status_code}',
                'timestamp': datetime.now().isoformat()
            }), response.status_code
            
    except requests.exceptions.Timeout:
        logging.error("FFD API request timed out")
        return jsonify({
            'success': False,
            'error': 'FFD API request timed out',
            'timestamp': datetime.now().isoformat()
        }), 504
        
    except requests.exceptions.RequestException as e:
        logging.error(f"FFD API request failed: {e}")
        return jsonify({
            'success': False,
            'error': f'FFD API request failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500
        
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/ffd-dams')
def get_ffd_dams():
    """Get only dam data from FFD telemetries"""
    try:
        telemetries_response = get_ffd_telemetries()
        telemetries_data = telemetries_response.get_json()
        
        if telemetries_data.get('success'):
            return jsonify({
                'success': True,
                'timestamp': telemetries_data['timestamp'],
                'last_updated': telemetries_data['last_updated'],
                'count': telemetries_data['dams_count'],
                'dams': telemetries_data['dams']
            })
        else:
            return telemetries_response
            
    except Exception as e:
        logging.error(f"Error getting dam data: {e}")
        return jsonify({
            'success': False,
            'error': f'Error getting dam data: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/ffd-headworks')
def get_ffd_headworks():
    """Get only headwork data from FFD telemetries"""
    try:
        telemetries_response = get_ffd_telemetries()
        telemetries_data = telemetries_response.get_json()
        
        if telemetries_data.get('success'):
            return jsonify({
                'success': True,
                'timestamp': telemetries_data['timestamp'],
                'last_updated': telemetries_data['last_updated'],
                'count': telemetries_data['headworks_count'],
                'headworks': telemetries_data['headworks']
            })
        else:
            return telemetries_response
            
    except Exception as e:
        logging.error(f"Error getting headwork data: {e}")
        return jsonify({
            'success': False,
            'error': f'Error getting headwork data: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    print("Starting Hydrological Situation Dashboard API...")
    print("FFD Telemetries Service Only")
    print(f"Available endpoints:")
    print(f"  - /api/health")
    print(f"  - /api/ffd-telemetries")
    print(f"  - /api/ffd-dams")
    print(f"  - /api/ffd-headworks")
    app.run(debug=True, host='0.0.0.0', port=5000)
