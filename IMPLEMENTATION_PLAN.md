# JARVIS Voice Assistant — Implementation Plan
> **livekit-agents v1.6.4 · Groq (STT + LLM) · Deepgram Aura-2 (TTS) · Intel i3 Local Hardware**
> Authoritative source. All paths are rooted at `C:\Projects\jarvis voice assistant\jarvis-assistant\`

---

## Audit Findings (Resolved Before Development)

| # | Issue | Status |
|---|---|---|
| `VoicePipelineAgent` does not exist in v1.6.4 | Replaced by `Agent` + `AgentSession` | ✅ Resolved |
| `livekit-plugins-groq` + `livekit-plugins-deepgram` not installed | Must install + add to requirements.txt | ⏳ Pending install |
| `.env` had `GROQ_API_KEY1` | Renamed to `GROQ_API_KEY` | ✅ Done |
| `silero.VAD.load()` is deprecated in v1.6.4 | `AgentSession` includes Silero VAD by default | ✅ Resolved |
| `ResilientChatSession(llm.ChatSession)` — wrong base class | `llm.FallbackAdapter` replaces custom class | ✅ Resolved |
| `session.start(record=False)` was flagged as TypeError | Confirmed valid in v1.6.4 `AgentSession.start()` | ✅ Corrected |
| Files written to AppData cache | Moved to project root | ✅ This file |

---

## Confirmed Architecture: `llm.FallbackAdapter`

Inspected source confirms `FallbackAdapter` handles Groq→Gemini failover natively:
- Takes a `list[LLM]` — tries each in order on failure
- `attempt_timeout=5.0` per provider
- `retry_on_chunk_sent=False` — safe mid-stream behaviour
- **No custom class needed.** The resilient LLM is one line:

```python
llm=llm.FallbackAdapter([groq_llm, gemini_llm], attempt_timeout=5.0)
```

---

## Confirmed API Pattern (v1.6.4)

```python
# Correct v1.6.4 entrypoint skeleton
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, llm

class JarvisAgent(Agent):
    def __init__(self):
        super().__init__(instructions="...")

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    session = AgentSession(
        stt=...,
        llm=llm.FallbackAdapter([groq_llm, gemini_llm]),
        tts=...,
        # vad= not needed — AgentSession includes Silero VAD by default
    )
    await session.start(agent=JarvisAgent(), room=ctx.room, record=False)
    await session.say("Systems online.", allow_interruptions=True)
```

---

## Flat Directory Structure (No `jarvis-core` subfolder)

```
C:\Projects\jarvis voice assistant\jarvis-assistant\
├── core\
│   ├── __init__.py
│   ├── config.py          # Type-safe env var validation (fails fast on boot)
│   └── worker.py          # LiveKit entrypoint — Agent + AgentSession
├── profiles\
│   ├── __init__.py
│   ├── base_profile.py    # Abstract Base Class
│   └── jarvis_personal.py # Personal assistant persona + tools
├── services\
│   ├── fallback_stt.py    # Moonshine ONNX Tiny (26MB) — offline STT
│   ├── fallback_tts.py    # Kokoro ONNX INT8 (88MB) — offline TTS
│   └── test_local_tts.py  # ✅ Isolation test — PASSED
├── frontend\              # Vite + React SPA (Phase 1 scaffold)
├── backend\static\
│   ├── kokoro-v1.0.int8.onnx
│   └── voices-v1.0.bin
├── .env                   # Keys: GROQ_API_KEY, GEMINI_API_KEY, DEEPGRAM_API_KEY,
│                          #       LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
├── requirements.txt
└── IMPLEMENTATION_PLAN.md  ← this file
```

---

## Phase 1 Implementation Steps

### Step 0 — Install Missing Plugins (Run once before coding)
```bash
pip install livekit-plugins-groq livekit-plugins-deepgram
```
Then add to `requirements.txt`:
```
livekit-plugins-groq>=1.0.0
livekit-plugins-deepgram>=1.0.0
```

---

### Step 1 — `core/config.py`
Type-safe boot-time validation. Required keys:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `GROQ_API_KEY`
- `DEEPGRAM_API_KEY`
- `GEMINI_API_KEY` ← mandatory (Groq failover engine, must be present at boot)

Fails fast with a clear error if any key is missing. No keys hardcoded.

---

### Step 2 — `core/worker.py`
LiveKit entrypoint. Rules:
- C-level thread locks (`OMP/OPENBLAS/MKL_NUM_THREADS=2`) at **absolute line 1** before any import
- `Agent` subclass with `instructions` injected from profile (not hardcoded)
- `AgentSession` wired with:
  - `stt=groq.STT(model="whisper-large-v3-turbo")` → PRIMARY
  - `llm=llm.FallbackAdapter([groq_llm, gemini_llm], attempt_timeout=5.0)` → RESILIENT
  - `tts=deepgram.TTS(model="aura-asteria-en", sample_rate=24000)` → PRIMARY
  - `vad=` omitted (AgentSession default Silero VAD built-in)
- `session.start(agent=..., room=ctx.room, record=False)`
- `await session.say(...)` for greeting

---

### Step 3 — `services/fallback_tts.py`
Local Kokoro ONNX INT8 fallback (already isolation-tested):
- Load `backend/static/kokoro-v1.0.int8.onnx` + `voices-v1.0.bin`
- Run in `ThreadPoolExecutor(max_workers=1)` — never block asyncio loop
- Call `kokoro.create(text, voice="am_adam", speed=1.0, lang="en-us")`
- Output: `.flatten()` → `rtc.AudioFrame(sample_rate=24000, num_channels=1)`

---

### Step 4 — `services/fallback_stt.py`
Local Moonshine ONNX Tiny fallback:
- Load via `useful-moonshine-onnx` (already in requirements.txt)
- Buffer `rtc.AudioFrame` chunks in `io.BytesIO` — no disk writes
- Run in `ThreadPoolExecutor(max_workers=1)`
- Input: 16kHz mono Linear16 PCM

---

### Step 5 — `profiles/jarvis_personal.py`
- Inherits `base_profile.py` ABC
- Returns system prompt string (JARVIS persona)
- Registers tools: `calculate`, `get_time`, `get_weather`, `web_search`

---

### Step 6 — Frontend (`frontend/`)
- Scaffold: `npm create vite@latest frontend -- --template react`
- Install: `@livekit/components-react`
- Static SPA — audio visualizer bars + room connection

---

## Audio Format Reference (Non-Negotiable)

| Layer | Format | Rate | Who handles it |
|---|---|---|---|
| Browser mic → LiveKit | Opus (WebRTC) | auto | Browser + LiveKit SDK |
| LiveKit → `worker.py` | Linear16 PCM (`rtc.AudioFrame`) | 16kHz mono | LiveKit SDK (transparent) |
| Groq Whisper STT | WAV / Linear16 PCM | 16kHz mono | `io.BytesIO` in RAM |
| Moonshine fallback | Linear16 PCM | 16kHz mono | `io.BytesIO` in RAM |
| Deepgram Aura TTS | Containerless Linear16 PCM | 24kHz | Pack → `rtc.AudioFrame` |
| Kokoro INT8 fallback | `float32 (1,N)` → `.flatten()` | 24kHz | Pack → `rtc.AudioFrame` |
| `worker.py` → LiveKit | Linear16 PCM (`rtc.AudioFrame`) | 24kHz | LiveKit SDK (transparent) |
| LiveKit → Browser | Opus (WebRTC) | auto | LiveKit + Browser |

> Python code **never touches Opus.** LiveKit SDK is the invisible Opus ↔ PCM boundary.

---

## ZDR (Zero Data Retention) Checklist

- [ ] LiveKit Cloud dashboard: Disable "Agent Insights" and "Recordings"
- [ ] `session.start(..., record=False)` — confirmed valid in v1.6.4
- [ ] Groq Console: Enable Zero Data Retention (ZDR) flag in Data Controls
- [ ] Deepgram: Toggle Zero Retention Mode on developer key
- [ ] Local: All audio buffers in `io.BytesIO` RAM only — no disk writes

---

## Phase 2 (After Phase 1 Is Stable)

- `profiles/sme_support.py` — business persona + PostgreSQL tool stubs
- Replace local ONNX fallbacks with SIP trunk transfer on outage
- BAA with Deepgram for HIPAA/GDPR compliance on medical/financial deployments

---

## Verification Sequence (No Big Bang Testing)

1. ✅ `services/test_local_tts.py` — Kokoro INT8 isolation test PASSED (17.7s, 24kHz)
2. ⏳ `pip install livekit-plugins-groq livekit-plugins-deepgram` — verify no import errors
3. ⏳ `python core/config.py` — boot-time env validation passes
4. ⏳ `python core/worker.py dev` — connects to LiveKit Cloud, no crashes
5. ⏳ LiveKit Agents Playground — live mic conversation end-to-end test
6. ⏳ Kill GROQ_API_KEY temporarily — verify FallbackAdapter switches to Gemini silently
