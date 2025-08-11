# 🕒 Simple Cron Job Setup for Hydrological Dashboard

## 🎯 Overview
This setup uses cron-job.org to directly call your local dashboard API every 6 hours to collect and store data.

## 🚀 How It Works
1. **cron-job.org** calls your local API endpoint every 6 hours
2. **Your local backend** fetches data from FFD APIs and stores it in SQLite
3. **Your frontend** displays the stored historical data when you open it

## 📋 Setup Steps

### Step 1: Expose Your Local API (Required)
Since cron-job.org needs to reach your local computer, you need to make your API accessible from the internet.

#### Option A: Use ngrok (Recommended - FREE)
1. **Download ngrok**: https://ngrok.com/download
2. **Extract and run**:
   ```bash
   # Start your backend first
   cd "C:\Users\4303sattar\Downloads\SU Dashboard\backend"
   python app.py
   
   # In another terminal, expose it
   ngrok http 5000
   ```
3. **Copy the ngrok URL** (looks like: `https://abc123.ngrok.io`)

#### Option B: Use localtunnel (Alternative - FREE)
1. **Install**: `npm install -g localtunnel`
2. **Run**: `lt --port 5000`
3. **Copy the URL** (looks like: `https://abc123.loca.lt`)

### Step 2: Create Cron Job
1. **Visit**: https://cron-job.org
2. **Sign up** with your API key: `yKQYvSACxlvkNsP8L5bwLtjeM63bdbRjr+MoYpmw/+k=`
3. **Create New Job**:
   - **Title**: `Hydro Data Collection`
   - **URL**: `[YOUR_NGROK_URL]/api/collect-data`
   - **Schedule**: Every 6 hours (0, 6, 12, 18)
   - **Save Responses**: Yes (for monitoring)

### Step 3: Test Setup
1. **Manual Test**: Visit `[YOUR_NGROK_URL]/api/collect-data` in browser
2. **Check Response**: Should see success message
3. **Verify Data**: Open your frontend locally to see updated data

## 🔄 Usage
1. **Keep ngrok running** (or restart when needed)
2. **Your dashboard** will automatically get fresh data every 6 hours
3. **Open frontend locally** anytime to see updated data

## 📊 Monitoring
- Check cron-job.org dashboard for execution logs
- Your backend will print collection status in console
- Frontend shows last update timestamps

## 🔧 Troubleshooting
- **Cron job fails**: Check if ngrok URL is still active
- **No data**: Verify backend is running on port 5000
- **Old data**: Check if cron job is actually running

## 💡 Pro Tips
- Keep a notepad with your current ngrok URL
- Restart ngrok if URL changes
- Check cron job logs if data seems stale
