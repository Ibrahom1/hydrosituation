@echo off
echo ================================================================
echo  🚀 Hydrological Data Collector - Auto Startup
echo ================================================================
echo.
echo This script will:
echo  ✅ Collect data from FFD APIs every 6 hours
echo  ✅ Store historical data in local database  
echo  ✅ Calculate trends automatically
echo  ✅ Run in background even when you're not using PC
echo.
echo Collection Schedule: 00:00, 06:00, 12:00, 18:00 daily
echo.
echo Press Ctrl+C to stop the collector
echo ================================================================
echo.

cd /d "%~dp0"
python data_collector.py

pause
