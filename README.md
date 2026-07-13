# 🏗️ J.A.R.V.I.S System Architecture

This document outlines the exact data travel paths, communication protocols, and component responsibilities for the J.A.R.V.I.S Personal Voice Assistant. It is designed to run entirely on constrained hardware (Intel i3, 8GB RAM) by offloading WebRTC routing to LiveKit Cloud and keeping only AI inference local.

---

## 1. Macro Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER DEVICE (Browser)                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ React UI (Static HTML/JS served by Python) + LiveKit Client SDK       │  │
│  │ • Handles getUserMedia (Mic/Speaker)                                 │  │
│  │ • Native WebRTC Opus Encoding/Decoding                               │  │
│  └───────┬───────────────────────────────────────────────┬───────────────┘  │
└──────────┼───────────────────────────────────────────────┼──────────────────┘
           │ 1. HTTPS (GET /api/token)                     │ 2. WebRTC Media
           │ (Fetches JWT)                                 │ (Opus / SRTP / DTLS)
           ▼                                               │
┌──────────────────────────────┐                           │
│  FASTAPI SERVER (Python)     │                           │
│  • Mints LiveKit JWTs        │                           │
│  • Serves static UI files    │                           │
└──────────────────────────────┘                           │
                                                           ▼
                                              ┌────────────────────────────┐
                                              │   LIVEKIT CLOUD (SFU)     │
                                              │  • Routes WebRTC packets   │
                                              │  • Opus <-> PCM Transcode │
                                              └────────────┬───────────────┘
                                                           │ 3. TCP Tunnel
                                                           │ (LiveKit Internal Proto)
                                                           │ (PCM Audio Frames)
                                                           ▼
                                              ┌────────────────────────────┐
                                              │  YOUR WORKER (Python)      │
                                              │  • Silero VAD (Gate)       │
                                              │  • STT (Groq/Moonshine)    │
                                              │  • LLM (Llama/Gemini)      │
                                              │  • TTS (Deepgram/Kokoro)   │
                                              │  • SQLite Memory          │
                                              └────────────────────────────┘
```

---

## 2. Communication Models & Protocol Definitions

| Connection Path | Protocol | Port | Data Format | Who Initiates |
| :--- | :--- | :--- | :--- | :--- |
| **Browser → FastAPI** | HTTPS (REST) | 8000 | JSON (Token Request) | Browser |
| **Browser ↔ LiveKit** | **WebRTC** (Media) | Random UDP | Opus Audio (SRTP encrypted) | Browser |
| **Browser ↔ LiveKit** | WebSocket (Signaling) | 443 | JSON (SDP/ICE candidates) | Browser |
| **Worker ↔ LiveKit** | **TCP** (LiveKit Proto) | 7880/443 | Binary RTC Frames | Worker |
| **Worker → Groq API** | HTTPS / WSS | 443 | JSON / PCM Streams | Worker |
| **Worker → Deepgram** | WSS (Streaming) | 443 | Text in / PCM out | Worker |

### The WebRTC / WebSocket Clarification
When the browser connects to LiveKit, it uses a **WebSocket for ~500ms** to exchange connection metadata (SDP offers, ICE candidates). The moment the WebRTC peer connection is established, the WebSocket goes idle. **All audio flows strictly over WebRTC (UDP)**. Your Python worker *never* uses WebSockets; it connects to LiveKit via a persistent, secure TCP connection managed entirely by the `livekit` SDK.

---

## 3. Data Travel Path (The Audio Lifecycle)

### The Input Path (User to LLM)
1.  **Capture:** Browser mic captures raw audio.
2.  **Encode (Browser):** Browser natively encodes to **Opus** (~24-32 kbps).
3.  **Transit (WebRTC):** Opus packets sent over UDP, encrypted via **SRTP**.
4.  **SFU Decode (LiveKit Cloud):** LiveKit decodes Opus back to raw **Linear16 PCM (16kHz, Mono)**.
5.  **Worker Receive (LiveKit SDK):** The Python SDK receives the PCM as an `rtc.AudioFrame` object.
6.  **VAD Gate (Worker):** Silero VAD inspects 20ms chunks. If speech is detected, the frame is buffered.
7.  **STT (Worker):** The buffered PCM (16kHz) is sent to Groq (cloud) or Moonshine (local ONNX). Output: **Plain Text**.
8.  **LLM (Worker):** Text is injected into the LLM context. LLM decides to reply or use a tool. Output: **Plain Text**.

### The Output Path (LLM to User)
1.  **TTS (Worker):** LLM text response is streamed to Deepgram (cloud) or Kokoro (local ONNX).
2.  **Format (Worker):** TTS outputs **Linear16 PCM (24kHz, Mono)**.
3.  **Worker Send (LiveKit SDK):** PCM is packed into a new `rtc.AudioFrame(24000, 1)` and pushed to the LiveKit TCP tunnel.
4.  **SFU Encode (LiveKit Cloud):** LiveKit encodes the 24kHz PCM down to **Opus**.
5.  **Transit (WebRTC):** Opus packets sent to browser via UDP/SRTP.
6.  **Decode (Browser):** Browser decodes Opus and plays through the speaker.

> **Critical Rule:** Your Python code **never** handles Opus encoding/decoding. The browser and LiveKit Cloud handle all Opus translation. Your worker acts exclusively in the realm of raw PCM and Text.

---

## 4. Component Responsibilities

### 4.1 The Browser Client
*   **Does:** Render UI, capture mic, play audio, handle WebRTC peer connections natively.
*   **Does NOT do:** Any AI processing, VAD, or formatting. It relies entirely on the browser's built-in WebRTC engine.
*   **Tech:** Vite (build-time only), React, `@livekit/components-react`.

### 4.2 The FastAPI Server
*   **Does:** Validate environment variables, generate cryptographically signed LiveKit JWTs, and serve the pre-compiled React static files.
*   **Does NOT do:** Handle audio, manage rooms, or know about WebRTC.
*   **Tech:** FastAPI, `PyJWT`, `python-dotenv`, `StaticFiles`.

### 4.3 LiveKit Cloud (The SFU)
*   **Does:** Act as a blind media switchboard. It takes 1 WebRTC stream from the browser and 1 TCP stream from the worker, and routes the audio between them. It handles Opus encoding, jitter buffering, and packet loss recovery.
*   **Does NOT do:** Transcription, AI inference, or inspect the contents of the audio.

### 4.4 The Python Worker (`core/worker.py`)
*   **Does:** The entire AI pipeline. It joins a LiveKit Room as a participant. It pulls PCM frames, runs VAD, transcribes, thinks, synthesizes, and pushes PCM frames back.
*   **Hardware constraints:** Strictly limited to 2 threads (`OMP_NUM_THREADS=2`) to prevent ONNX runtime from freezing the i3 CPU during local fallback scenarios.

---

## 5. The Internal Worker Pipeline (Fallback Matrix)

Inside `worker.py`, the architecture relies on custom wrapper classes to handle edge-failures without dropping the LiveKit room connection.

```text
[LiveKit SDK] --> rtc.AudioFrame (16kHz PCM)
       │
       ▼
┌──────────────────┐
│   SILERO VAD     │  (Blocks non-speech. Prevents wasting CPU/API calls on noise)
└────────┬─────────┘
         │ (Confirmed Speech Buffer)
         ▼
┌──────────────────┐     ┌─────────────────────┐
│   GROQ WHISPER   │────►│  CUSTOM FALLBACK    │
│   (Cloud STT)    │ X   │  WRAPPER CLASS      │──── Text ──┐
└──────────────────┘     │  (Catches Timeout)  │            │
                         └─────────┬───────────┘            │
                                   │                        │
                         ┌─────────▼───────────┐            │
                         │   MOONSHINE ONNX    │────────────┘
                         │   (Local STT)       │
                         └─────────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────────┐
                                          │   GROQ LLAMA 3.3    │
                                          │   (Cloud LLM)       │
                                          └─────────┬───────────┘
                                                    │ Text Response
                                                    ▼
                                          ┌─────────────────────┐
                                          │   DEEPGRAM AURA-2   │
                                          │   (Cloud TTS)       │─────┐
                                          └─────────┬───────────┘     │
                                                    │                   │
                                          ┌─────────▼───────────┐     │
                                          │   KOKORO ONNX       │     │
                                          │   (Local TTS)       │─────┤
                                          └─────────────────────┘     │
                                                                      │
                                                                      ▼
                                                   [LiveKit SDK] <-- rtc.AudioFrame (24kHz PCM)
```

## 6. Privacy & Security Posture
*   **In-Transit:** All browser audio is encrypted via mandatory WebRTC SRTP/DTLS. The SFU-to-Worker link is encrypted via TLS.
*   **In-Memory Processing:** Audio is buffered in volatile RAM (`io.BytesIO`). It is never written to a disk log.
*   **Zero Retention APIs:** Groq and Deepgram are configured with zero-data-retention flags.
*   *Note on Compliance: This architecture follows best-practice privacy engineering to minimize data footprint.*

### Corrected Code Reference
The worker exclusively uses the modern v1.6.4 `AgentSession` execution loop with explicit VAD parsing:
```python
    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
        vad=silero.VAD.load(activation_threshold=0.6, min_speech_duration=0.3, min_silence_duration=0.8)
    )

    await session.start(agent=jarvis_agent, room=ctx.room, record=False)
    await session.say(profile.greeting_message, allow_interruptions=True)
```

---

## 7. How to Run (Production Mode - Zero Node.js)

Because FastAPI serves the static files, your production machine only runs Python.

1. **Build Frontend** (Do this once, anywhere):
```bash
cd frontend
npm install
npm run build   # Outputs to frontend/dist/
```

2. **Run Backend** (Your i3 Machine - 2 Terminals):
```bash
# Terminal 1: Serves /api/token AND the static frontend files
uvicorn core.server:app --host 0.0.0.0 --port 8000

# Terminal 2: Connects to LiveKit Cloud, waits for rooms
python core/worker.py dev
```

---

## 8. Open-Source Configuration (Zero-Cost Setup)

This repository is optimized for a frictionless, zero-cost launch. You do **not** need complex Google Cloud credentials, service accounts, or a linked credit card to run the core tools.

### Out-of-the-Box Features (No Keys Required)
The following tools work instantly upon cloning the repo:
* **Web Search:** DuckDuckGo (`ddgs`) Scout & Deep-Dive architecture (Safe context limits).
* **Weather:** Open-Meteo geocoding and forecasting.
* **Local Agenda Manager:** Automatically reads and writes to a local `agenda.md` file. Zero API latency.
* **Math, Time, System Media Automation** (Local Python built-ins).

### Optional Upgrades (Single Text Keys)
To unlock JARVIS's full potential, simply create a `.env` file in the root directory and drop in the following text keys:

```env
# 1. YouTube Playout & Fact-Checking (Free Tier)
# Get this from Google Cloud Console > API & Services > Credentials (No billing required)
GOOGLE_CLOUD_API_KEY="AIzaSy..."

# 2. Email Dispatch System (100 Free Emails / Day)
# Get this from SendGrid > Settings > API Keys (No credit card required)
SENDGRID_API_KEY="SG.YourActualSendGridKeyHere"
JARVIS_EMAIL_IDENTITY="jarvis.assistant@yourdomain.com"
```

Once your `.env` is set, restart the worker, and JARVIS will automatically begin using these endpoints to send research emails, fact-check rumors, and launch YouTube media autonomously!
