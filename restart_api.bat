@echo off
echo Stopping old API servers...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 >nul
echo Starting API server...
cd src
start "Perfect Books API" python api.py
echo API server started!
