# JARVIS AI Voice Assistant — Final Implementation Plan

## Selected Configuration

| Decision | Choice |
|----------|--------|
| **Deployment Target** | Hugging Face Spaces (free, shareable) |
| **STT Engine** | Moonshine (tiny, ~26MB RAM) |
| **TTS Engine** | Kokoro-ONNX (82M params, 8 languages, 54 voices) |
| **Primary LLM** | Groq (llama-3.3-70b-versatile) via LPU hardware |
| **Fallback LLM** | Gemini 2.0 Flash (free tier) |
| **Frontend** | Bundled inside same HF Docker container |
| **Wake Word** | Browser-based (Porcupine Web / Picovoice) |
| **Persona System** | Frontend voice ID flag (Jarvis/Veronica) — v1 feature |
| **Tool Set** | Calculator (simpleeval), Time, Weather (Open-Meteo), DuckDuckGo Search |
| **Memory** | SQLite per-session (current) + defer vector DB to v2 |

---

## Architecture Overview

```
                    HUGGING FACE SPACE (Docker)
                     Port 7860 | 2 vCPU | 16GB RAM
+-----------------------------------------------+
|  +------------------+  +--------------------+  |
|  |  Next.js Frontend|  |  FastAPI Backend   |  |
|  |  (Static Served) |  |                    |  |
|  |                   |  |  WS /ws endpoint  |  |
|  |  Mic Capture ----|--|-> In-Mem Buffer   |  |
|  |  (250ms slices)  |  |       v           |  |
|  |                   |  |  Moonshine STT    |  |
|  |  Porcupine Wake   |  |       v           |  |
|  |  Word (browser)   |  |  Groq (primary)  |  |
|  |                   |  |  Gemini (fallback)|  |
|  |  Audio Queue <----|--|--- Tool Registry |  |
|  |  Playback Engine  |  |       v           |  |
|  |  (Web Audio API)  |  |  Kokoro-ONNX TTS |  |
|  |                   |  |  (sentence-chunk) |  |
|  |  Persona Selector |  |       v           |  |
|  |  + Blend Slider   |  |  WAV -> WebSocket|  |
|  +------------------+  +--------------------+  |
+-----------------------------------------------+
```

## Data Flow (Turn-by-Turn)

1. **Wake Word** — Porcupine (browser) detects "Jarvis" → opens WebSocket
2. **Mic Capture** — MediaRecorder slices 250ms Opus chunks → binary over WS
3. **Moonshine STT** — In-memory buffer → np.float32 normalize → transcribe → text
4. **Groq LLM** — System prompt + tool schema → recognizes intent → returns JSON tool call or text
5. **Tool Exec** — simpleeval("45*8") → "360" → fed back to Groq for final response
6. **Gemini Fallback** — If Groq fails/rate-limited → Gemini 2.0 Flash handles query
7. **Kokoro TTS** — Split reply by .,!,? → each sentence → WAV chunk → WS send_bytes
8. **Browser Play** — decodeAudioData → AudioBuffer → queue scheduled → gapless playback

## File Structure (Final)

```
jarvis-assistant/
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile                    # HF Spaces deployment
├── IMPLEMENTATION_PLAN.md        # This file
├── README.md                     # Updated
├── TODO.md                       # Checklist
├── backend/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, WebSocket /ws endpoint
│   ├── config.py
│   ├── schemas.py
│   ├── websocket_manager.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ai_orchestrator.py    # Dual-LLM + tool routing
│   │   ├── intent_classifier.py
│   │   ├── response_generator.py
│   │   └── conflict_resolver.py
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── stt.py                # ElevenLabs (legacy)
│   │   └── tts.py                # ElevenLabs (legacy)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── llm_service.py    # Groq + Gemini dual router
│   │   │   ├── stt_service.py    # Moonshine wrapper
│   │   │   └── tts_service.py    # Kokoro-ONNX wrapper
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── tool_registry.py
│   │   │   ├── tool_executor.py
│   │   │   └── builtin/
│   │   │       ├── calculator_tool.py
│   │   │       ├── time_tool.py
│   │   │       └── weather_tool.py
│   │   ├── duckduckgo_service.py
│   │   ├── wikipedia_service.py
│   │   ├── newsdata_service.py
│   │   └── factcheck_service.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── models.py
│   │   ├── crud.py
│   │   └── init_db.py
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       ├── exceptions.py
│       ├── language.py
│       └── sanitizers.py
├── client/                       # Next.js frontend
│   ├── package.json
│   ├── tsconfig.json
│   ├── postcss.config.mjs
│   ├── next.config.ts
│   ├── public/
│   └── src/
│       ├── app/
│       │   ├── page.tsx
│       │   ├── layout.tsx
│       │   └── globals.css
│       ├── components/
│       │   ├── VoiceInterface.tsx
│       │   ├── VoiceCaptureManager.tsx
│       │   ├── VoicePlaybackManager.tsx
│       │   └── CustomVoiceMixer.tsx
│       ├── hooks/
│       │   └── useWebSocket.ts
│       └── store/
│           └── chatStore.ts
├── frontend/                     # Vanilla JS (legacy)
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests/
│   └── integration/
│       └── test_full_system.py
├── realtime_assistant.py
├── test_ai_pipeline.py
├── test_api_compatibility.py
├── test_tools.py
├── test_user_snippet.py
└── test.wav
```
## Implementation Phases

### Phase 0: Foundation Fixes (Pre-requisite)
- Add all missing `__init__.py` files (7 directories) — DONE
- Fix `frontend/app.js` corruption — DONE
- Clean up `main.py` imports (remove unused, use absolute paths) — DONE
- Ensure `uvicorn backend.main:app` boots without errors — DONE
- Install missing deps (`slowapi`, `openai`, `duckduckgo-search`) — DONE

### Phase 1: Moonshine STT Integration

**Files to modify:** `backend/services/ai/stt_service.py`

Key code:
```python
import numpy as np
import moonshine

class STTService:
    def __init__(self):
        self.model = moonshine.load_model("moonshine/tiny")

    def transcribe(self, audio_bytes: bytes) -> str:
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        result = self.model.transcribe(audio_np)
        return result.strip() if result else ""

stt_service = STTService()
```
Dep: `pip install useful-moonshine numpy`

### Phase 2: Kokoro-ONNX TTS Integration

**Files to modify:** `backend/services/ai/tts_service.py`
**Assets needed:** `kokoro-v1.0.onnx` + `voices-v1.0.bin`

Key code:
```python
import io, re, asyncio
import soundfile as sf
from kokoro_onnx import Kokoro

class TTSService:
    def __init__(self, model_path="backend/static/kokoro-v1.0.onnx", voices_path="backend/static/voices-v1.0.bin"):
        self.engine = Kokoro(model_path, voices_path)
        self.voice_map = {"jarvis": "am_adam", "veronica": "af_bella", "heart": "af_heart"}

    def get_voice_id(self, persona: str) -> str:
        return self.voice_map.get(persona.lower(), "am_adam")

    async def stream_speech(self, text: str, voice_id: str, send_fn):
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if not sentence.strip(): continue
            samples, sample_rate = self.engine.create(sentence, voice=voice_id, speed=1.0, lang="en-us")
            byte_io = io.BytesIO()
            sf.write(byte_io, samples, sample_rate, format='WAV', subtype='PCM_16')
            await send_fn(byte_io.getvalue())
            await asyncio.sleep(0.01)

tts_service = TTSService()
```
Dep: `pip install kokoro-onnx soundfile`

### Phase 3: Dual-LLM Router (Groq Primary + Gemini Fallback)

**Files to modify:** `backend/services/ai/llm_service.py`

Key code:
```python
import os, json
from groq import Groq
from google import genai
from simpleeval import simple_eval

class LLMService:
    def __init__(self):
        self.groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.gemini = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.primary_model = "llama-3.3-70b-versatile"
        self.fallback_model = "gemini-2.0-flash"

    async def chat_complete(self, messages: list, tools: list = None) -> str:
        try:
            return await self._call_groq(messages, tools)
        except Exception as e:
            print(f"Groq failed: {e}. Falling back to Gemini...")
            return await self._call_gemini(messages)

    async def _call_groq(self, messages: list, tools: list = None) -> str:
        kwargs = {"model": self.primary_model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = self.groq.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        if msg.tool_calls:
            return await self._handle_tool_calls(msg, messages, kwargs["model"])
        return msg.content

    async def _handle_tool_calls(self, msg, messages, model):
        messages.append(msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            if tc.function.name == "run_calculator":
                from simpleeval import simple_eval
                result = str(simple_eval(args.get("expression", "0")))
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": result})
        final = self.groq.chat.completions.create(model=model, messages=messages)
        return final.choices[0].message.content

    async def _call_gemini(self, messages: list) -> str:
        gemini_messages = []
        for m in messages:
            if "content" in m and m["content"]:
                role = "model" if m["role"] == "assistant" else "user"
                gemini_messages.append({"role": role, "parts": [{"text": m["content"]}]})
        response = self.gemini.models.generate_content(model=self.fallback_model, contents=gemini_messages)
        return response.text

llm_service = LLMService()
```
Dep: `pip install groq google-genai simpleeval`

### Phase 4: Tool Registry Integration

Integrate tool schemas with Groq function calling:
- Calculator: `simpleeval` — safe expression evaluation
- Time: `datetime.now()` — zero deps
- Weather: Open-Meteo API — free, no key
- DuckDuckGo Search: `duckduckgo-search` — free, no key

Tool schema format for Groq:
```python
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_calculator",
            "description": "Evaluates math expressions safely. Use for any calculations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "e.g. '45 * 8'"}
                },
                "required": ["expression"]
            }
        }
    }
]
```

### Phase 5: Next.js Frontend Components

**Files to create:**

| Component | File | Purpose |
|-----------|------|---------|
| VoiceCaptureManager | `client/src/components/VoiceCaptureManager.tsx` | Mic -> WS 250ms slices |
| VoicePlaybackManager | `client/src/components/VoicePlaybackManager.tsx` | Audio queue -> speakers |
| CustomVoiceMixer | `client/src/components/CustomVoiceMixer.tsx` | Persona blend slider |
| JarvisDashboard | `client/src/app/page.tsx` | Assembles all components |

Key patterns:

**VoiceCaptureManager** — Captures mic, streams binary chunks:
```typescript
const startRecording = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true }
  });
  const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
  recorder.ondataavailable = async (event) => {
    if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
      socket.send(await event.data.arrayBuffer());
    }
  };
  recorder.start(250);
};
```

**VoicePlaybackManager** — Queue-based gapless playback:
```typescript
socket.onmessage = async (event) => {
  if (typeof event.data === "string") return;
  const audioBuffer = await audioContext.decodeAudioData(event.data);
  const source = audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(audioContext.destination);
  if (nextStartTimeRef.current < audioContext.currentTime)
    nextStartTimeRef.current = audioContext.currentTime;
  source.start(nextStartTimeRef.current);
  nextStartTimeRef.current += audioBuffer.duration;
};
```

**CustomVoiceMixer** — Persona blend slider:
```typescript
const handleSliderUpdate = (e) => {
  const value = parseFloat(e.target.value);
  socket.send(JSON.stringify({
    type: "update_voice_blend", base_voice: "am_adam",
    mod_voice: "am_michael", alpha: value
  }));
};
```

### Phase 6: Dockerfile for HF Spaces

```dockerfile
FROM python:3.10-slim

WORKDIR /code

RUN apt-get update && apt-get install -y ffmpeg libasound2-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /code/client
RUN npm install && npm run build
WORKDIR /code

EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860", "--ws", "wsproto"]
```

### Phase 7: WebSocket Endpoint in main.py

The `/ws` endpoint handles both binary audio and JSON control messages:
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    buffer = io.BytesIO()
    session_history = []
    active_voice = "am_adam"

    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                data = json.loads(message["text"])
                if data.get("type") == "set_voice":
                    active_voice = data["voice_id"]
                if data.get("type") == "speech_ended":
                    buffer = io.BytesIO()
                continue

            if "bytes" in message:
                buffer.write(message["bytes"])
                buffer.seek(0)
                raw = buffer.read()
                if len(raw) < 2048: continue

                transcript = stt_service.transcribe(raw)
                if not transcript: continue

                reply = await llm_service.chat_complete(
                    session_history + [{"role": "user", "content": transcript}],
                    tools=TOOLS_SCHEMA
                )

                session_history += [{"role": "user", "content": transcript},
                                    {"role": "assistant", "content": reply}]
                await websocket.send_json({"type": "bot_response_text", "text": reply})
                await tts_service.stream_speech(reply, active_voice, websocket.send_bytes)
                buffer = io.BytesIO()

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        buffer.close()
```

## Deployment Checklist

### Hugging Face Space Setup
- [ ] Create HF Space with Docker SDK (NOT Gradio/Streamlit)
- [ ] Set secrets: GROQ_API_KEY, GEMINI_API_KEY
- [ ] Push repository with Dockerfile
- [ ] Verify port 7860 exposed
- [ ] Test: https://username-space.hf.space/health

### WebSocket Proxy Handling
- HF Spaces proxies wss://username-space.hf.space/ws
- Must bind to port 7860 (HF default)
- Use --ws wsproto for WebSocket support

### Wake Word (Porcupine Web)
- Runs entirely in browser — no server load
- Free tier: up to 100 wake word detections/day
- Uses WebAssembly in a Web Worker thread
- On "Jarvis" detected -> open WebSocket to backend
- On "Veronica" detected -> set persona flag + open WS

## Voice Mixing Matrix (Optional)

```python
import numpy as np
def create_custom_persona(voice_1_vec, voice_2_vec, alpha=0.5):
    """Linear interpolation: 0 = 100% voice_1, 1 = 100% voice_2"""
    return (1.0 - alpha) * voice_1_vec + (alpha * voice_2_vec)
```

## Cost Breakdown

| Service | Cost | Limits |
|---------|------|--------|
| Hugging Face Spaces | Free | 2 vCPU, 16GB RAM, 50GB storage, 48h sleep |
| Groq (Primary LLM) | Free tier | 30 req/min, 1440 req/day |
| Gemini 2.0 Flash | Free tier | 60 req/min |
| Open-Meteo (Weather) | Free | No key, 10k req/day |
| DuckDuckGo Search | Free | No key |
| Porcupine Wake Word | Free tier | 100 detections/day |
| **Total** | **$0** | |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| HF Space sleeps after 48h | cron-job.org ping /health every 30 min, or $0.60/hr paid tier |
| WebSocket 404 on HF proxy | Bind port 7860, test /ws path early |
| CPU throttle on 2 vCPUs | Moonshine tiny + Kokoro-82M ONNX fit comfortably |
| Groq rate limits | Gemini fallback handles automatically |
| API key leaks | Set as HF Secrets, never in .env committed |
