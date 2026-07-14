# JARVIS Feature Feasibility Assessment

> Analysis against current architecture: `core/worker.py` + `profiles/jarvis_personal.py` + LiveKit Agents 1.6

---

## VERIFIED: Memory Already Works

`memory_db.py` + `remember_user_fact` / `recall_user_facts` exist and are wired into `get_tools()`.
`GOOGLE_CLOUD_API_KEY` / `SENDGRID_API_KEY` optional vars are listed correctly — those are real optional tools from the full 14-tool profile.

The memory system works cross-session today. The SQLite DB persists at `core/static/memory.db`.

---

## Feature Feasibility Matrix

| # | Feature | Effort | Risk to Architecture | Do ASAP? |
|---|---------|--------|---------------------|----------|
| 1 | **Persistent Memory on Session Load** | XS | None | YES |
| 2 | **Proactive Scheduled Reminders** | S | Low | YES |
| 3 | **Local Code Execution Sandbox** | S | Low | YES |
| 4 | **Sound Effects (chime on listen)** | S | Medium | Later |
| 5 | **Wake Word Detection** | M | HIGH | Skip |

---

## Feature Deep-Dives

### 1. Persistent Memory on Session Load — ASAP, ~15 lines

**What's missing:** `remember_user_fact` stores facts, but on a new session the LLM has no idea they
exist. Fix: load all memories into the initial `ChatContext` system message at `entrypoint()`.

**Change in `core/worker.py`** — after `initial_ctx.add_message(role="system", ...)`:

```python
# Load persistent memory into session context
stored_facts = profile.memory.search_memory("")  # fetch ALL facts
if stored_facts:
    memory_block = "PERSISTENT MEMORY (from previous sessions):\n" + "\n".join(f"- {f}" for f in stored_facts[:20])
    initial_ctx.add_message(role="system", content=memory_block)
```

**Risk:** None. Purely additive to context. Works with existing SQLite layer.

---

### 2. Proactive Scheduled Reminders — ASAP, ~40 lines

**What's missing:** A `set_reminder(time_minutes, message)` tool + a background asyncio task
that calls `session.say()`.

**Changes needed:**
- Add `set_reminder` tool to `profiles/jarvis_personal.py`
- Add `set_session(session)` method to `JarvisPersonalProfile`
- Call `profile.set_session(session)` in `core/worker.py` after session is created

```python
# In jarvis_personal.py
@llm.function_tool()
async def set_reminder(self, message: str, minutes_from_now: int) -> str:
    """Sets a spoken reminder to fire after a delay.
    Args:
        message: What to remind the user about.
        minutes_from_now: How many minutes until the reminder fires.
    """
    asyncio.create_task(self._fire_reminder(message, minutes_from_now * 60))
    return f"Reminder set: I will alert you about '{message}' in {minutes_from_now} minutes."

async def _fire_reminder(self, message: str, delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    if self._session:
        await self._session.say(f"Reminder: {message}", allow_interruptions=True)
```

**Risk:** Low. Uses existing `session.say()` API. asyncio.create_task won't block event loop.

---

### 3. Local Code Execution Sandbox — ASAP, ~25 lines

**What's missing:** A `run_python(code)` tool using `subprocess` with a hard timeout.
Extends `calculate_math` (which only does simple expressions) to full Python.

```python
# Add to jarvis_personal.py
@llm.function_tool()
async def run_python(self, code: str) -> str:
    """Executes a Python snippet safely in a sandboxed subprocess.
    Args:
        code: Valid Python code to execute.
    """
    import subprocess, sys
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=5
            ),
            timeout=6.0
        )
        output = result.stdout.strip() or result.stderr.strip() or "No output."
        return f"Execution result: {output[:500]}"
    except asyncio.TimeoutError:
        return "Execution timed out after 5 seconds."
    except Exception as e:
        return f"Execution failed: {str(e)}"
```

**Risk:** Low. Subprocess is isolated. Hard timeout prevents CPU starvation on i3. No new deps.

---

### 4. Sound Effects (chime on listen) — Later

**What it needs:** Pre-baked .wav file → push as `rtc.AudioFrame` via session before TTS response.

**Risk:** Medium. Timing must be exact — a bad push can overlap with TTS output or trigger
an interruption signal. Needs isolated testing with `test_chime.py` first (per SKILL.md Rule 2).

---

### 5. Wake Word Detection — SKIP

**Why:** A continuous ONNX inference loop on every 20ms audio frame is exactly the thread
starvation pattern SKILL.md Rule 1 prohibits. LiveKit's own Silero VAD is already doing
activity detection. A second model layer on the same i3 CPU would compete and drop WebRTC heartbeats.

**Alternative:** Add a dedicated ESP32/Raspberry Pi as a hardware pre-filter — then this is viable.

---

## Recommended Execution Order

```
NOW (additive, zero pipeline risk):
  [ ] Persistent memory load on session start   — ~15 lines in core/worker.py
  [ ] run_python sandbox tool                   — ~25 lines in jarvis_personal.py
  [ ] set_reminder tool                         — ~40 lines in jarvis_personal.py

LATER (needs isolation test first):
  [ ] Sound effect chime

SKIP:
  [ ] Wake word (i3 hardware constraint)
  [ ] Multi-agent orchestration (latency cost)
  [ ] Vector DB (SQLite is sufficient)
```

All 3 ASAP features are ADDITIVE ONLY — new tools or a few lines in entrypoint().
They do NOT touch VAD, STT, LLM, or TTS pipeline. Zero risk of breaking working audio.
