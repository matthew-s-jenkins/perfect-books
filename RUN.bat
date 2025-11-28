@echo off
title Perfect Books - Personal Finance Simulator

REM Check if .env exists (optional for Perfect Books)
REM if not exist ".env" (
REM     echo WARNING: .env file not found - using defaults
REM )

echo ========================================
echo   PERFECT BOOKS
echo   Personal Finance Simulator
echo ========================================
echo.
echo Starting server...
echo.
echo Application URL: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Check if virtual environment exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Navigate to src directory and start Flask backend in background
cd src
start "Perfect Books - Backend" /B python api.py

REM Wait for backend to start
echo Waiting for server to start...
timeout /t 3 /nobreak >nul

REM Open browser
echo Opening browser...
start http://localhost:5000

REM Keep window open
echo.
echo Server is running. Close this window to stop the server.
echo.
pause >nul
