@echo off
title Perfect Books
color 0A

echo.
echo ============================================================
echo Perfect Books - Starting...
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During installation, check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM Run the launcher
python start.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo [ERROR] An error occurred. See messages above.
    echo.
    pause
)
