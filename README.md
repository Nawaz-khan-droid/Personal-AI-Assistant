---
title: Jarvis Voice Assistant
sdk: docker
emoji: 🎙️
colorFrom: blue
colorTo: indigo
---

# J.A.R.V.I.S AI Voice Assistant

Production-grade voice assistant with browser-based AudioWorklet capture, energy-based VAD, Moonshine STT, Groq/Gemini LLM routing, Kokoro-ONNX TTS, and a 4-tool function-calling registry. Deployable to Hugging Face Spaces at $0 cost.

## Architecture

```
[Browser - AudioWorklet @ 16kHz]
  → VAD (energy-based, auto/manual toggle)
  → Raw PCM Int16 chunks
  → WebSocket ──────────────────────────────────┐
                                                │
FastAPI /ws                                       │
  → STT (asyncio.to_thread → Moonshine)         │
  → LLM (Tenacity 429/Timeout → Groq) ──► Gemini│
  → Tools (calculate, time, weather, search)    │
  → TTS (asyncio.to_thread → Kokoro ONNX)       │
  → WAV chunks ─────────────────────────────────┘
  → WebSocket
  → Browser [decodeAudioData → gapless queue]
```

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Capture** | AudioWorklet + ScriptProcessorNode | Chrome-safe, raw PCM, no encode/decode |
| **VAD** | Energy-based (RMS + hangover) | Zero dependencies, runs in browser |
| **STT** | Moonshine (tiny) | ~26MB RAM, variable-length, CPU-optimized |
| **Primary LLM** | Groq (llama-3.3-70b-versatile) | ~300 tok/s on LPU, generous free tier |
| **Fallback LLM** | Gemini 2.0 Flash | Free tier, robust API |
| **TTS** | Kokoro-ONNX (82M) | 54 voices, 8 languages, ONNX-optimized |
| **Backend** | FastAPI + WebSocket + wsproto | Async streaming, HF Spaces proxy-safe |
| **Frontend** | Next.js 16 + Tailwind v4 | Static export, bundled in same container |
| **Database** | SQLite (SQLAlchemy) | Per-session conversation history |
| **Tools** | simpleeval, Open-Meteo, DDG, zoneinfo | All free, no API keys |

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 20+
- API keys: `GROQ_API_KEY` (required), `GEMINI_API_KEY` (optional fallback)

### Local Development

```bash
# 1. Python deps
pip install -r requirements.txt

# 2. Frontend deps
cd client && npm install && cd ..

# 3. Start backend (terminal 1)
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# 4. Start frontend (terminal 2)
cd client && npm run dev
```

### Docker (HF Spaces)

```bash
docker build -t jarvis-assistant .
docker run -p 7860:7860 \
  -e GROQ_API_KEY=your_key \
  -e GEMINI_API_KEY=your_key \
  jarvis-assistant
```

## WebSocket Protocol

### Client → Server (Binary)
Raw PCM Int16, 16kHz mono, 250ms chunks.

### Client → Server (JSON)
```json
{"type": "set_voice_profile", "mode": "preset", "voice_id": "am_adam"}
{"type": "set_voice_profile", "mode": "mix", "base_voice": "am_adam", "mod_voice": "am_michael", "alpha": 0.3}
{"type": "save_custom_mix", "name": "my_voice", "base_voice": "am_adam", "mod_voice": "am_michael", "alpha": 0.5}
{"type": "trigger_preview", "text": "System test."}
{"type": "speech_ended"}
{"type": "clear_history"}
```

### Server → Client (JSON)
```json
{"type": "stt_text", "text": "what is the weather"}
{"type": "thinking", "status": "Processing..."}
{"type": "bot_response_text", "text": "It is 22°C in London."}
{"type": "custom_voice_saved", "name": "my_voice", "path": "custom_voices/my_voice.npy"}
```

### Server → Client (Binary)
PCM-16 WAV sentence chunks.

## Tool Registry

| Tool | Implementation | API Key | Description |
|------|---------------|---------|-------------|
| `calculate` | simpleeval (AST-safe) | None | Math expressions |
| `get_current_time` | zoneinfo (stdlib) | None | IANA timezone lookup |
| `get_weather` | Open-Meteo API | None | Current conditions + forecast |
| `web_search` | DuckDuckGo | None | Web search results |

## Deployment

### Hugging Face Spaces

1. Create Space with **Docker** SDK (CPU, not GPU)
2. Set secrets: `GROQ_API_KEY`, `GEMINI_API_KEY`
3. Push repo (includes multi-stage `Dockerfile`)
4. Space auto-builds at `https://<user>-<space>.hf.space`

**Port:** 7860 (HF Spaces default), `--ws wsproto` for WebSocket proxy support.

## Cost = $0

| Service | Limit |
|---------|-------|
| Hugging Face Spaces | 2 vCPU, 16GB RAM, 50GB storage |
| Groq | 30 req/min, 1440 req/day |
| Gemini 2.0 Flash | 60 req/min |
| Open-Meteo | 10k req/day |
| DuckDuckGo | Unlimited |
