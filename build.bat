@echo off
echo Installing dependencies...

REM Check if pip is available
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: pip is not available. Please ensure Python is installed and pip is in your PATH.
    goto :eof
)

REM Install required Python packages
echo Installing tkinter (usually bundled with Python, but good to ensure pip knows about it or for virtual envs)
python -m pip install tk
echo Installing Playwright...
python -m pip install playwright
echo Installing Playwright browser drivers (will install Chromium by default)...
python -m playwright install chromium

echo.
echo Dependencies installed.
echo.
echo To run the application, execute:
echo python roblox_uploader.py
echo.

:eof
pause
