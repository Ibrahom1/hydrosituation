@echo off
echo 🚀 Starting SU Dashboard Backend Server...
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo ❌ Virtual environment not found
    echo Please run setup.bat first
    pause
    exit /b 1
)

REM Activate virtual environment and start server
call venv\Scripts\activate
echo ✅ Virtual environment activated
echo.
echo 🌐 Starting Flask server on http://localhost:5000
echo 📱 Your dashboard frontend can now upload media files!
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py
