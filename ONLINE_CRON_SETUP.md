# 🌐 Online Cron Job Setup for Local Dashboard

## 📋 Overview
This setup allows an online cron job to collect hydrological data every 6 hours and sync it to your local dashboard when you turn on your PC.

## 🎯 How It Works
1. **Online Collector**: Runs on Replit/GitHub Actions every 6 hours
2. **Data Storage**: Stores latest data in accessible cloud location
3. **Local Sync**: Your dashboard syncs cloud data when PC starts
4. **Continuous Updates**: Even if PC is off for days, you get all missed data

## 🚀 Setup Steps

### Step 1: Create Online Data Collector

#### Option A: Replit (Easiest - FREE)
1. **Visit**: https://replit.com
2. **Create Account**: Sign up for free
3. **New Repl**: Choose "Python" template
4. **Upload**: Copy `cloud_collector.py` to your Repl
5. **Install Dependencies**: Add to `requirements.txt`:
   ```
   requests==2.31.0
   ```
6. **Test Run**: Click "Run" to test data collection
7. **Setup Cron**: Use Replit's cron feature or UptimeRobot

#### Option B: GitHub Actions (FREE)
1. **Create Repository**: Make new GitHub repo
2. **Add Workflow**: Create `.github/workflows/collect.yml`:
   ```yaml
   name: Collect Hydro Data
   on:
     schedule:
       - cron: '0 */6 * * *'  # Every 6 hours
     workflow_dispatch:  # Manual trigger
   
   jobs:
     collect:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - name: Set up Python
           uses: actions/setup-python@v3
           with:
             python-version: '3.9'
         - name: Install dependencies
           run: pip install requests
         - name: Collect data
           run: python cloud_collector.py
         - name: Commit data
           run: |
             git config --local user.email "action@github.com"
             git config --local user.name "GitHub Action"
             git add latest_hydro_data.json
             git commit -m "Update hydro data $(date)" || exit 0
             git push
   ```

### Step 2: Configure Data Access URL

After setting up your collector, update your local dashboard:

1. **Open**: `backend/app.py`
2. **Find Line**: `cloud_url = "https://your-replit-app.replit.dev/latest_hydro_data.json"`
3. **Replace With**:
   - **Replit**: `https://your-repl-name.your-username.repl.co/latest_hydro_data.json`
   - **GitHub**: `https://raw.githubusercontent.com/username/repo/main/latest_hydro_data.json`
   - **Gist**: `https://gist.githubusercontent.com/username/gist-id/raw/hydro_data.json`

### Step 3: Test Local Sync

1. **Start Backend**: `python app.py`
2. **Test Sync**: Visit `http://localhost:5000/api/sync-cloud-data`
3. **Check Response**: Should see `{"success": true, "message": "Cloud data synced successfully"}`

### Step 4: Verify Dashboard Integration

1. **Open Dashboard**: `http://localhost:8080`
2. **Check Console**: Should see "✅ Cloud data synced successfully"
3. **View Data**: Charts should show latest data from cloud

## 🔧 Advanced Options

### GitHub Gist Storage (Private Data)
```python
# Add to cloud_collector.py
def upload_to_gist(data, token):
    gist_data = {
        "description": "Hydro Dashboard Data",
        "public": False,  # Private gist
        "files": {
            "hydro_data.json": {
                "content": json.dumps(data, indent=2)
            }
        }
    }
    
    headers = {'Authorization': f'token {token}'}
    response = requests.post('https://api.github.com/gists', 
                           json=gist_data, headers=headers)
    return response.json()
```

### Webhook Integration
```python
# Add to cloud_collector.py
def notify_webhook(data):
    """Notify your local PC when data is updated"""
    webhook_url = "https://your-ngrok-tunnel.ngrok.io/api/webhook"
    requests.post(webhook_url, json=data, timeout=5)
```

### Data Validation
```python
# Add to store_telemetry_data function
def validate_data(data):
    """Validate data before storing"""
    required_fields = ['name', 'inflow_discharge', 'outflow_discharge']
    return all(field in data for field in required_fields)
```

## 📊 Benefits

✅ **24/7 Data Collection**: Never miss updates, even when PC is off
✅ **Zero Cost**: All platforms offer generous free tiers
✅ **Automatic Sync**: Dashboard updates when you start PC
✅ **Historical Backfill**: Get all missed data automatically
✅ **Offline Resilience**: Local database always has latest sync
✅ **Manual Control**: Force sync anytime with `/api/sync-cloud-data`

## 🔍 Monitoring

### Check Collector Status
- **Replit**: View logs in Replit console
- **GitHub**: Check Actions tab for run history
- **Local**: Monitor `/api/sync-cloud-data` response

### Data Freshness
```javascript
// Add to your dashboard
function checkDataFreshness() {
    fetch('/api/sync-cloud-data')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const syncTime = new Date(data.timestamp);
                const hoursOld = (Date.now() - syncTime) / (1000 * 60 * 60);
                console.log(`Data is ${hoursOld.toFixed(1)} hours old`);
            }
        });
}
```

## 🆘 Troubleshooting

### Common Issues
1. **"Cloud fetch failed"**: Check your cloud_url in app.py
2. **"Data error"**: Verify collector is running and storing data
3. **"Connection timeout"**: Cloud service might be down, retry later
4. **Empty data**: First run might be empty, wait for next collection cycle

### Debug Commands
```bash
# Test cloud collector locally
python cloud_collector.py

# Check local sync
curl http://localhost:5000/api/sync-cloud-data

# View stored data
sqlite3 backend/hydro_history.db "SELECT * FROM telemetry_history ORDER BY fetched_at DESC LIMIT 5;"
```

## 🎉 Final Result

Your dashboard now has:
- **Continuous data collection** via online cron job
- **Automatic synchronization** when PC starts
- **Historical data preservation** even during PC downtime  
- **Real-time updates** from cloud-collected data
- **Zero deployment** required - everything runs locally!

Perfect solution for 24/7 data monitoring without deploying your entire dashboard!
