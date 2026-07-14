# LiveKit server + UI server + worker
# All three must start within 10s for HF Spaces readiness probe

# Start LiveKit server in dev mode (background)
livekit-server --dev --port 7880 &
LIVEKIT_PID=$!
echo "LiveKit server starting on :7880 (pid=$LIVEKIT_PID)"

# Wait for LiveKit to be ready
for i in $(seq 1 20); do
  if curl -sf http://localhost:7880 > /dev/null 2>&1; then
    echo "LiveKit server ready"
    break
  fi
  sleep 0.5
done

# Start the web server (UI + tokens) on port 7860 (background)
uvicorn core.server:app --host 0.0.0.0 --port 7860 &
WEB_PID=$!
echo "Web server starting on :7860 (pid=$WEB_PID)"

# Start the LiveKit worker (foreground)
echo "Starting LiveKit worker..."
exec python -m core.worker
