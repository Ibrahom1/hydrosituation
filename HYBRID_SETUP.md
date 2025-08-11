# Hybrid Data Collection Setup

## Overview
Use an online cron service to collect and store data, then sync to your local dashboard when PC starts.

## Step 1: Online Data Collector (Cron-job.org)

### Create Python Script for Data Collection
```python
# online_collector.py
import requests
import json
from datetime import datetime
import sqlite3
import os

def collect_ffd_data():
    """Collect data from FFD API and store in cloud database"""
    try:
        # Fetch from FFD API
        dams_response = requests.get('https://ffd.gov.pk/api/dams', timeout=60)
        headworks_response = requests.get('https://ffd.gov.pk/api/headworks', timeout=60)
        
        if dams_response.ok and headworks_response.ok:
            data = {
                'timestamp': datetime.now().isoformat(),
                'dams': dams_response.json(),
                'headworks': headworks_response.json()
            }
            
            # Store to cloud database (SQLite file or JSON API)
            store_to_cloud(data)
            print(f"✅ Data collected at {datetime.now()}")
        else:
            print(f"❌ API Error: Dams {dams_response.status_code}, Headworks {headworks_response.status_code}")
            
    except Exception as e:
        print(f"❌ Collection failed: {e}")

def store_to_cloud(data):
    """Store data to accessible cloud location"""
    # Option A: Upload to GitHub Gist
    # Option B: Store in Dropbox/Google Drive
    # Option C: Use free database service
    pass

if __name__ == "__main__":
    collect_ffd_data()
```

### Setup Online Cron Job
1. **Visit**: https://cron-job.org (FREE)
2. **Create Account**: Free tier allows 5 jobs
3. **Add Job**:
   - URL: `https://replit.com/@yourusername/hydro-collector`
   - Schedule: `0 */6 * * *` (every 6 hours)
   - Method: GET

## Step 2: Modify Your Local Dashboard

### Update Backend to Sync Data
```python
# Add to your app.py
@app.route('/api/sync-cloud-data')
def sync_cloud_data():
    """Sync data from cloud storage to local database"""
    try:
        # Download latest data from cloud storage
        cloud_data = fetch_from_cloud()
        
        # Update local database
        with get_db_connection() as conn:
            # Update your local SQLite with cloud data
            store_cloud_data_locally(conn, cloud_data)
        
        return jsonify({'success': True, 'message': 'Data synced'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def fetch_from_cloud():
    """Fetch latest data from cloud storage"""
    # Implement based on your cloud storage choice
    pass
```

### Auto-Sync on Dashboard Load
```javascript
// Add to your script.js
async function autoSyncOnLoad() {
    try {
        const response = await fetch('http://localhost:5000/api/sync-cloud-data');
        if (response.ok) {
            console.log('✅ Cloud data synced');
        }
    } catch (e) {
        console.log('⚠️ Cloud sync failed, using local data');
    }
}

// Call on page load
document.addEventListener('DOMContentLoaded', function() {
    autoSyncOnLoad();  // Sync first
    setTimeout(refreshAllData, 1000);  // Then refresh UI
});
```

## Step 3: Cloud Storage Options

### Option A: GitHub Gist (FREE)
```python
def store_to_github_gist(data):
    """Store data as GitHub Gist"""
    gist_data = {
        "files": {
            "hydro_data.json": {
                "content": json.dumps(data, indent=2)
            }
        }
    }
    
    headers = {'Authorization': 'token YOUR_GITHUB_TOKEN'}
    response = requests.post('https://api.github.com/gists', 
                           json=gist_data, headers=headers)
    return response.json()
```

### Option B: Google Sheets API (FREE)
```python
def store_to_google_sheets(data):
    """Store data to Google Sheets"""
    # Use Google Sheets API to append data
    # Each row = timestamp + dam/headwork data
    pass
```

### Option C: JSONBin.io (FREE)
```python
def store_to_jsonbin(data):
    """Store to JSONBin.io"""
    headers = {
        'Content-Type': 'application/json',
        'X-Master-Key': 'YOUR_JSONBIN_KEY'
    }
    response = requests.put('https://api.jsonbin.io/v3/b/YOUR_BIN_ID', 
                          json=data, headers=headers)
    return response.json()
```
