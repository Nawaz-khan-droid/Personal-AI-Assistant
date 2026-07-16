---
title: JARVIS Voice Assistant
emoji: 🤖
colorFrom: cyan
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

<p align="center">
  <img src="assets/banner_v2.png" alt="JARVIS Voice Assistant Banner" width="100%"/>
</p>

<p align="center">
  <a href="https://livekit.io/agents"><img src="https://img.shields.io/badge/LiveKit-Agents%20v1.6-00e5ff?style=flat-square&logo=webrtc&logoColor=white" alt="LiveKit Agents v1.6"/></a>
  <a href="https://console.groq.com"><img src="https://img.shields.io/badge/LLM-Groq%20Llama%203.3%2070B-00e5ff?style=flat-square&logo=meta&logoColor=white" alt="Groq Llama 3.3 70B"/></a>
  <a href="https://console.deepgram.com"><img src="https://img.shields.io/badge/STT-Deepgram%20Nova--2-00e5ff?style=flat-square&logoColor=white" alt="Deepgram Nova-2 STT"/></a>
  <a href="https://console.deepgram.com"><img src="https://img.shields.io/badge/TTS-Deepgram%20Aura--2-00e5ff?style=flat-square&logoColor=white" alt="Deepgram Aura-2 TTS"/></a>
  <a href="https://github.com/usefulsensors/moonshine"><img src="https://img.shields.io/badge/Fallback%20STT-Moonshine%20ONNX-555555?style=flat-square&logoColor=white" alt="Moonshine ONNX STT"/></a>
  <a href="https://github.com/hexgrad/kokoro"><img src="https://img.shields.io/badge/Fallback%20TTS-Kokoro%20ONNX-555555?style=flat-square&logoColor=white" alt="Kokoro ONNX TTS"/></a>
  <a href="https://react.dev"><img src="https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61dafb?style=flat-square&logo=react&logoColor=black" alt="React + Vite"/></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/></a>
  <a href="https://github.com/Nawaz-khan-droid"><img src="https://img.shields.io/badge/GitHub-Nawaz--khan--droid-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub Profile"/></a>
</p>

<p align="center">
  <strong>A real-time voice AI assistant with dual personas, 15 tools, and cloud-first + local fallback architecture.</strong>
</p>

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  PROCESS 1 — Web Server (uvicorn core.server:app) │
│  Port: 7860                                       │
│                                                   │
│   POST /api/token  →  JWT token minting           │
│   GET  /api/health →  health check                │
│   GET  /           →  React SPA (built frontend)  │
└──────────────────────────┬───────────────────────┘
                           │  separate process
                           ▼
┌──────────────────────────────────────────────────┐
│  PROCESS 2 — LiveKit Agent (python -m core.worker)│
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │  EAR — Speech Detection                     │  │
│  │  Silero VAD ──► Deepgram Nova-2  (primary)  │  │
│  │                └► Moonshine ONNX (fallback)  │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │  BRAIN — Language Model                     │  │
│  │  Groq Llama 3.3 70B      (primary)          │  │
│  │  └► Gemini 2.0 Flash     (fallback)         │  │
│  │  15 × function_tool()    (tool suite)       │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │  VOICE — Speech Synthesis                   │  │
│  │  Deepgram Aura-2 TTS     (primary)          │  │
│  │  └► Kokoro ONNX          (fallback)         │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## Personas

| Persona | TTS Voice | Greeting |
|---------|-----------|---------|
| **JARVIS** | Aura-2 Neptune (deep male) | *"System active. Communication channels are stable, Sir."* |
| **VERONICA** | Aura-2 Aurora (female) | *"Veronica core online. Awaiting your instructions."* |

Switch persona: use a room name containing `veronica` (e.g. `veronica-session-1234`).

## Tool Suite (15 Tools)

| # | Tool | Key Required |
|---|------|-------------|
| 1 | `get_current_time` | None |
| 2 | `get_world_time` | None (Open-Meteo) |
| 3 | `get_weather_data` | None (Open-Meteo) |
| 4 | `search_web` | None (DuckDuckGo) |
| 5 | `scrape_page` | None |
| 6 | `calculate_math` | None |
| 7 | `remember_user_fact` | None (SQLite) |
| 8 | `recall_user_facts` | None (SQLite) |
| 9 | `open_website_system` | None |
| 10 | `control_media` | None |
| 11 | `add_agenda_event` | None |
| 12 | `view_agenda_events` | None |
| 13 | `search_youtube_media` | `GOOGLE_CLOUD_API_KEY` |
| 14 | `verify_claim_truth` | `GOOGLE_CLOUD_API_KEY` |
| 15 | `send_research_email` | `SENDGRID_API_KEY` + `JARVIS_EMAIL_IDENTITY` |

## Session & Memory

**Does each session restart the chat?**
No. `AgentSession` maintains a persistent `ChatContext` for the full room session. Every utterance is appended; full history is sent to the LLM each turn. When you disconnect, that context ends — but the **SQLite memory persists across all sessions**.

**Cross-Session Memory:**
`remember_user_fact` / `recall_user_facts` store facts in `core/static/memory.db`. Say *"remember my favorite color is blue"* → stored permanently. Next session: *"what's my favorite color?"* → recalled from DB.

## Quick Start (Local)

### Prerequisites
- Python 3.10+, Node.js 20+
- [LiveKit Cloud account](https://cloud.livekit.io) — free tier works
- [Groq API key](https://console.groq.com) — free tier works
- [Deepgram API key](https://console.deepgram.com) — free tier works

### Setup
```bash
git clone https://github.com/Nawaz-khan-droid/Personal-AI-Assistant.git
cd Personal-AI-Assistant
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
cp .env.example .env
# Edit .env with your API keys
```

### Run
```bat
start_local.bat
```
Open `http://localhost:7860` and enter your `JARVIS_UI_PASSWORD`.

## Environment Variables

Set required keys as **Repository Secrets** in HF Spaces → Settings → Variables and secrets:

| Variable | Description | Required |
|----------|-------------|----------|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL (`wss://...`) | ✅ |
| `LIVEKIT_API_KEY` | LiveKit Cloud API key | ✅ |
| `LIVEKIT_API_SECRET` | LiveKit Cloud API secret | ✅ |
| `GROQ_API_KEY` | Groq API key (LLM) | ✅ |
| `DEEPGRAM_API_KEY` | Deepgram API key (STT + TTS) | ✅ |
| `JARVIS_UI_PASSWORD` | Password to access the UI | ✅ |
| `GEMINI_API_KEY` | Gemini 2.0 Flash — LLM fallback | Optional |
| `GOOGLE_CLOUD_API_KEY` | YouTube search + Fact Check tools | Optional |
| `SENDGRID_API_KEY` | Email dispatch tool | Optional |
| `JARVIS_EMAIL_IDENTITY` | Sender address for email tool | Optional |
| `GROQ_LLM_MODEL` | Override model (default: `llama-3.3-70b-versatile`) | Optional |
| `DEEPGRAM_TTS_MODEL` | Override voice (default: `aura-2-neptune-en`) | Optional |

## Project Structure

```
Personal-AI-Assistant/
├── core/
│   ├── config.py           # Pydantic settings, .env validation
│   ├── server.py           # FastAPI: token endpoint + SPA serving
│   └── worker.py           # LiveKit agent: full pipeline + tools
├── profiles/
│   ├── base_profile.py     # Abstract profile interface
│   └── jarvis_personal.py  # JARVIS/Veronica personas + 15 tools
├── services/
│   ├── fallback_stt.py     # Moonshine ONNX STT (offline fallback)
│   ├── fallback_tts.py     # Kokoro ONNX TTS (offline fallback)
│   └── memory_db.py        # SQLite persistent memory wrapper
├── frontend/               # React + Vite + LiveKit Components
├── assets/
│   ├── banner.png          # README banner
│   └── icon.png            # App icon
├── Dockerfile              # Multi-stage: Node 20 build → Python 3.10 runtime
├── requirements.txt
├── start_local.bat         # Windows dev launcher
└── startup.sh              # Linux / Docker launcher
```

## Deploying to Hugging Face Spaces

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space) → SDK: **Docker**
2. Push this repo to the Space remote
3. Add all required secrets in **Settings → Variables and secrets**
4. Watch the **Logs** tab — build takes 3–5 min. Look for:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:7860
   JARVIS worker connected to LiveKit Cloud
   ```

## End-to-End Test Checklist

```
[ ] Space builds without Docker errors
[ ] Space URL loads the React login page
[ ] Wrong password  →  "Unauthorized" error
[ ] Correct password  →  voice UI appears
[ ] JARVIS persona: deep male TTS voice
[ ] Veronica persona: female TTS voice
[ ] "What time is it?"               →  get_current_time fires
[ ] "What's the weather in London?"  →  get_weather_data fires
[ ] "Remember my favorite color is blue"  →  stored in SQLite
[ ] "What's my favorite color?"           →  recalled from SQLite
[ ] "Search for latest AI news"      →  search_web fires
[ ] Barge-in works (interrupt mid-sentence, JARVIS stops)
[ ] /api/health returns {"status": "ok"}
[ ] Container stable after 5 min idle
```

---

<p align="center">
  <sub>Built with <a href="https://livekit.io/agents">LiveKit Agents</a> · <a href="https://console.groq.com">Groq</a> · <a href="https://deepgram.com">Deepgram</a> · <a href="https://react.dev">React</a> · <a href="https://fastapi.tiangolo.com">FastAPI</a></sub>
</p>
