# JARVIS AI Voice Assistant — Implementation Status

## Legend
- [x] Completed
- [~] In progress

## Pipeline

- [x] Browser AudioWorklet capture (raw PCM Int16 @ 16kHz)
- [x] Energy-based VAD (RMS threshold + hangover timer)
- [x] Auto-detect mode + manual override toggle
- [x] Zustand store for shared voice system state
- [x] Moonshine STT (async, thread-offloaded)
- [x] Dual-LLM router: Groq primary + Gemini fallback
- [x] Tenacity retry (429 + timeout only, exponential backoff)
- [x] 4 tools: calculate, get_current_time, get_weather, web_search
- [x] Tool execution via ToolExecutor + registry
- [x] Kokoro-ONNX TTS (sentence-chunked, thread-offloaded)
- [x] Voice blending (linear interpolation of voice vectors)
- [x] Custom voice save/load as .npy
- [x] Gapless audio playback queue

## Infrastructure

- [x] FastAPI WebSocket (/ws) with binary + JSON
- [x] IP-based WS rate limiter (30 turns/min)
- [x] audio buffer capped at 10s (no OOM)
- [x] session_history trimmed to 20 turns
- [x] ONNX threads capped at 1 (2 vCPU env)
- [x] Multi-stage Dockerfile (Node 20 build → Python 3.10 slim)
- [x] HEALTHCHECK on /health
- [x] wsproto for HF Spaces WebSocket proxy
- [x] Static export Next.js bundled in same container
- [x] CORS restricted to explicit origins

## Deployment

- [ ] Create HF Space with Docker SDK
- [ ] Set GROQ_API_KEY + GEMINI_API_KEY secrets
- [ ] Verify cold start on HF Spaces
- [ ] Verify WebSocket on HF proxy (wss://)
- [ ] Verify TTS audio delivery through proxy

## Future (v2)

- [ ] AudioWorklet → full duplex streaming
- [ ] Silero VAD via WASM (more accurate than energy-based)
- [ ] Qdrant vector DB for cross-session memory
- [ ] Porcupine Web wake word
- [ ] More Kokoro voices (Hindi, French, Spanish)
- [ ] Tauri desktop wrapper
