@echo off
echo ========================================
echo   JARVIS Local Dev Startup
echo ========================================

REM Check GROQ_API_KEY
if "%GROQ_API_KEY%"=="" (
    echo.
    echo ERROR: GROQ_API_KEY not set.
    echo   set GROQ_API_KEY=your_key_here
    echo.
    exit /b 1
)

set LIVEKIT_URL=ws://127.0.0.1:7880
set LIVEKIT_API_KEY=devkey
set LIVEKIT_API_SECRET=secret

echo [1/3] Starting LiveKit server...
start "LiveKit" livekit-server.exe --dev --port 7880
timeout /t 2 /nobreak >nul
echo   LiveKit running on ws://127.0.0.1:7880

echo [2/3] Starting web server (UI + tokens)...
start "JARVIS-Web" python dev_server.py
timeout /t 2 /nobreak >nul
echo   Web UI at http://127.0.0.1:7860

echo [3/3] Starting LiveKit worker...
echo   Worker connecting to LiveKit...
python -m backend.main dev
