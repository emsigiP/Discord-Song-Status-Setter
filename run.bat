@echo off
title Spotify Lyrics Discord Sync
echo ====================================================
echo  Spotify Lyrics Discord Status Sync - Autostart
echo ====================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Python is not installed or not in your PATH.
    echo Please download and install Python from https://www.python.org/
    echo Make sure to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)

echo Checking and installing dependencies...
python -m pip install --quiet -r requirements.txt
if %errorlevel% neq 0 (
    echo [Warning] pip install failed, attempting manual install...
    pip install --quiet winrt-Windows.Media.Control winrt-Windows.Foundation winrt-Windows.Foundation.Collections requests python-dotenv flask
)

echo.
echo Starting Web Dashboard Control Panel...
echo (A browser window should open automatically in a few seconds)
echo.
python src/app.py

pause
