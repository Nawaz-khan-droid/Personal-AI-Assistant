---
name: jarvis_developer
description: Architectural rules, workflow constraints, and best practices for developing the LiveKit JARVIS Voice Assistant on the specific local hardware.
---

# JARVIS Voice Assistant Development Rules

When working on the JARVIS Voice Assistant codebase, you MUST adhere to the following architectural constraints, strict code safety guidelines, and multi-file processing workflows. This project runs on an Intel i3 processor with severe hardware limitations and utilizes low-latency WebRTC via LiveKit Cloud.

## 1. Hardware Awareness & Environment Throttling
*   **The Thread Starvation Choke-Point:** The Intel i3 host system is highly susceptible to thread starvation and CPU blocking. Heavy operations can cause WebRTC heartbeats to drop, resulting in immediate disconnects.
*   **Rule:** Never run heavy ML models synchronously on the main asyncio event loop.
*   **Rule:** Always declare C-level environment-level thread limits at the absolute top of your entrypoint script (`core/worker.py`), before importing any machine learning extensions, ONNX runtimes, or LiveKit plugins:
    ```python
    import os
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["OPENBLAS_NUM_THREADS"] = "2"
    os.environ["MKL_NUM_THREADS"] = "2"
    ```
*   **Rule:** Prefer cloud-based routing (Groq for Whisper-large-v3-turbo STT and Llama-3.3 LLM; Deepgram for Aura-2 TTS) as the primary execution path. Local ONNX models (Moonshine Tiny and Quantized Kokoro-ONNX) must strictly act as ephemeral, offline failbacks to protect system resources.

## 2. No "Big Bang" Testing & Phase-Driven Isolation
*   **Rule:** Do NOT boot the WebRTC server, the UI, the STT, the LLM, and the TTS all simultaneously when debugging a new feature.
*   **Rule:** Break complex, multi-file tasks down into distinct, sequential architectural phases. 
*   **Workflow:** Test components in complete isolation first. Write minimal, independent Python scripts within `services/` (e.g., a 15-line `test_local_tts.py`) to verify that an ONNX runtime instance can load within thread limits and write an audio payload directly to a local file before dropping it into the live LiveKit pipeline.
*   **Rule:** The primary engineering agent must manually review, verify, and trace every line of code emitted. Do not delegate critical compilation checks or class structural inheritance loops to lower-quality subagents.

## 3. Storage and File Execution Rules
*   **Rule:** All code modifications, environment configs, frontend scaffolds, and backend modules must be saved directly within the following absolute local project directory path:
    `C:\Projects\jarvis voice assistant\jarvis-assistant`
*   **Rule:** Do not write files or save execution progress into temporary sandboxes, generic system temp tracks, or AppData environments.
*   **Rule:** Actively purge and delete dead code or legacy files that are no longer used to avoid memory overhead and compiler namespace conflicts. This includes wiping out old standalone FastAPI websocket loops (`websocket_manager.py`) or custom frontend `AudioWorklet` VAD code blocks, as LiveKit handles connection persistence and Silero VAD natively.

## 4. LiveKit Core and Media Frame Packing Rules
*   **Rule (Anti-Hallucination):** Stop "vibe coding" asynchronous WebRTC logic or raw audio buffer manipulation. If a LiveKit class or method fails, do not guess the parameters. Inspect the source library API signatures explicitly using python `inspect` or `grep` before generating structural changes.
*   **Rule (Audio Frame Wrapping):** Custom local TTS or fallback layers cannot stream raw primitives or raw `bytes` straight to the LiveKit transport. You must pack PCM arrays into explicit `livekit.rtc.AudioFrame` objects specifying precise sample counts, channel counts, and sample rates:
    ```python
    from livekit import rtc
    frame = rtc.AudioFrame(data=pcm_data, sample_rate=24000, num_channels=1, samples_per_channel=count)
    ```
*   **Rule (Audio Format & Sample Rates — Non-Negotiable):** The audio format contract is fixed and must never be guessed:
    - The LiveKit SDK **automatically** decodes incoming WebRTC Opus to **Linear16 PCM at 16kHz mono** before handing frames to your code. You never touch Opus.
    - Feed Groq Whisper STT with **16kHz mono Linear16 PCM** (via `io.BytesIO` WAV bytes, never disk files).
    - Deepgram Aura TTS returns **containerless Linear16 PCM chunks at 24kHz**. Pack directly into `rtc.AudioFrame(sample_rate=24000, num_channels=1)`.
    - Kokoro ONNX fallback returns a `float32 ndarray` of shape `(1, N)`. Always call `.flatten()` before packing into `rtc.AudioFrame`.
    - The LiveKit SDK **automatically** re-encodes your outbound `rtc.AudioFrame` PCM back to Opus for the browser. You never touch Opus.
*   **Rule (VAD Parameter Name Warning):** Do NOT hallucinate the Silero VAD initialization parameters. The kwarg is exclusively `activation_threshold`, NOT `threshold`. Passing `threshold` will cause an instant `TypeError` and crash the worker silently on connection.
    ```python
    vad_plugin = silero.VAD.load(activation_threshold=0.6, min_speech_duration=0.3, min_silence_duration=0.8)
    ```
*   **Rule (Barge-In Interruption Management):** Any asynchronous synthesis generator loops inside custom plugins must explicitly intercept `asyncio.CancelledError`. The exact millisecond LiveKit issues a cancellation signal (user barge-in), the loop must instantly break, flush internal audio buffers, and halt background ONNX inference tracking to immediately release the i3 CPU cores for the new user sequence.

## 5. Architectural Reusability (The Proxy Profile Pattern)
*   **Rule:** Do not hardcode raw prompts, system configuration variables, or tools inside your main execution engine loop (`core/worker.py`).
*   **Implementation:** Follow a strict configuration-driven `AgentProfile` factory pattern. `core/worker.py` must act as a clean, generic execution pipeline that accepts injected profile identities. This allows the codebase to transition instantly from a personal assistant track to an SME business customer support bot by changing a single parameter string.
*   **Rule (The Proxy Delegation Pattern):** Multi-cloud resilient failovers (e.g., falling back from Groq to Gemini Lite during a 429 rate limit) must wrap LiveKit's native `llm.LLM` and `llm.ChatSession` interfaces cleanly via proxy delegation. Do not attempt to modify private, underlying client attributes mid-session, as this introduces severe asynchronous race conditions.

## 6. Zero Data Retention (ZDR) Privacy Protocol
*   **Rule:** Maintain strict, stateless, ephemeral processing limits across all pipeline endpoints to guarantee SME data sovereignty:
    *   **LiveKit Cloud:** Telemetry tracking, cloud recordings, and transcript logs must be disabled globally via the project dashboard settings.
    *   **Groq Cloud:** Account setups must toggle Zero Data Retention (ZDR) flags to prevent text strings from lingering on multi-tenant cloud storage.
    *   **Local Processing:** Never write temporary conversation audio snippets down to the physical hard drive. Maintain all transient byte blocks strictly inside volatile RAM memory arrays (`io.BytesIO`).
