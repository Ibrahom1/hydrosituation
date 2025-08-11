@echo off
echo 🚀 Setting up SU Dashboard Backend...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo ✅ Python found
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

echo.

REM Activate virtual environment and install dependencies
echo 📚 Installing dependencies...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ✅ Backend setup complete!
echo.
echo 🏃‍♂️ To start the backend server:
echo    1. Run: start_backend.bat
echo    2. Or manually: 
echo       - venv\Scripts\activate
echo       - python app.py
echo.
pause
