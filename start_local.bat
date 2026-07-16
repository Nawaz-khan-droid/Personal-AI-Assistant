@echo off
echo ========================================
echo   JARVIS Local Dev Startup
echo ========================================

REM Python will load the GROQ_API_KEY from the .env file automatically.
set LIVEKIT_URL=ws://127.0.0.1:7880
set LIVEKIT_API_KEY=devkey
set LIVEKIT_API_SECRET=secret

echo [1/3] Starting LiveKit server...
start "LiveKit" livekit-server.exe --dev --port 7880
timeout /t 2 /nobreak >nul
echo   LiveKit running on ws://127.0.0.1:7880

echo [2/3] Starting web server (UI + tokens)...
start "JARVIS-Web" uvicorn core.server:app --port 7860
timeout /t 2 /nobreak >nul
echo   Web UI at http://127.0.0.1:7860

echo [3/3] Starting LiveKit worker...
echo   Worker connecting to LiveKit...
python -m core.worker dev
