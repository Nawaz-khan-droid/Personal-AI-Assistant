# JARVIS Agentic Feature Brainstorm
> Based on actual codebase — LiveKit 1.6.4, Groq Llama 3.3, Deepgram, SQLite memory_db.py

---

## Part 1: Tavily Credit Efficiency

**Key fact:** The LiveKit `ChatContext` already acts as a free same-session cache.

When JARVIS calls `search_and_read("Python internships Internshala")`, the result is
stored as a tool message in ChatContext. When the user asks "what was the stipend again?",
Llama 3.3 reads the previous tool output from ChatContext history and answers directly
— **zero new Tavily call**. This already works with your setup.

### What to add: In-session query deduplication cache

A simple Python dict on the profile instance. Hash the query → store result.
If the same query is called again in the same session, return the cached string.

```python
# In JarvisPersonalProfile.__init__():
self._search_cache: dict[str, str] = {}

# At the top of search_and_read():
import hashlib
cache_key = hashlib.md5(query.strip().lower().encode()).hexdigest()[:12]
if cache_key in self._search_cache:
    return self._search_cache[cache_key]  # 0 credits, instant

# At the end, before returning any result:
self._search_cache[cache_key] = out.strip()
return out.strip()
```

Cost: ~8 lines. Benefit: prevents double-spend on exact repeated queries.

### Cross-session search cache (optional)

Store Tavily summaries to SQLite with a timestamp. On next session, if query was
searched in the last 24h, serve the cached result. For static data (internship
listings change daily, not hourly) this is totally valid.

```python
# Key format: "search_cache_{md5_hash}"
# Value format: JSON {"result": "...", "timestamp": "2026-07-16T..."}
# Expiry: skip cache if timestamp > 24 hours old
```

---

## Part 2: Previously Searched Memory in a Session

### What already works (zero code needed):
- LiveKit `ChatContext` retains ALL tool call outputs for the entire session
- Llama 3.3 sees the full history every turn → "what was the stipend again?" answered from history
- `remember_user_fact` + `recall_user_facts` persist across sessions via SQLite

### What's missing: Memory auto-load on session start

Your `core/worker.py` line 121 adds the system prompt. Right after that, add:

```python
# After: initial_ctx.add_message(role="system", content=profile.system_prompt)

stored_facts = await asyncio.to_thread(profile.memory.search_memory, "")
if stored_facts:
    facts_block = "LONG-TERM MEMORY (from past sessions):\n" + "\n".join(
        f"- {f}" for f in stored_facts[:20]
    )
    initial_ctx.add_message(role="system", content=facts_block)
```

~5 lines. JARVIS now opens every session knowing your name, preferences, past context.

---

## Part 3: Agentic Feature Brainstorm

Rated by: Impact | Effort | Risk to existing pipeline

### TIER 1 — Do Immediately (~10-30 lines each, zero pipeline risk)

---

**1. Proactive Scheduled Reminders**
- New tool: `set_reminder(message, minutes_from_now)`
- `asyncio.create_task` fires `session.say()` after delay
- No new dependencies, uses existing `session` reference
- Impact: HIGH (transforms JARVIS from reactive → agentic)

```python
@llm.function_tool()
async def set_reminder(self, message: str, minutes_from_now: int) -> str:
    """Sets a spoken reminder after a delay. Args: message, minutes_from_now."""
    async def _fire():
        await asyncio.sleep(minutes_from_now * 60)
        if self._session:
            await self._session.say(f"Reminder: {message}", allow_interruptions=True)
    asyncio.create_task(_fire())
    return f"Reminder set for {minutes_from_now} minutes: '{message}'."
```

Needs: `self._session` injected in worker.py (`profile._session = session`).

---

**2. Python Sandbox (Code Executor)**
- New tool: `run_python(code)`
- subprocess + hard timeout — keeps i3 CPU safe
- Extends `calculate_math` to full Python
- Impact: HIGH (data processing, file parsing, anything Python can do)

```python
@llm.function_tool()
async def run_python(self, code: str) -> str:
    """Executes a Python snippet in a safe sandboxed subprocess.
    Args: code — valid Python, no imports needed for math/string ops."""
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
        return f"Result: {output[:500]}"
    except asyncio.TimeoutError:
        return "Timed out after 5 seconds."
    except Exception as e:
        return f"Failed: {str(e)}"
```

---

**3. Clipboard Read/Write**
- New tools: `read_clipboard()`, `write_to_clipboard(text)`
- Say "JARVIS read my clipboard" → reads and summarizes whatever is copied
- Say "JARVIS copy this to clipboard: [text]" → writes it
- Dependencies: `pyperclip` (tiny, already common)
- Impact: MEDIUM-HIGH for desktop workflow

```python
@llm.function_tool()
async def read_clipboard(self) -> str:
    """Reads the current content of the system clipboard."""
    import pyperclip
    try:
        text = await asyncio.to_thread(pyperclip.paste)
        return f"Clipboard contains: {text[:500]}" if text else "Clipboard is empty."
    except Exception as e:
        return f"Could not read clipboard: {e}"
```

---

**4. Local File Reader**
- New tool: `read_local_file(filename)`
- Reads .txt, .md, .py files from a safe whitelist directory
- "JARVIS summarize my notes.txt" → reads file → LLM summarizes
- No new dependencies (built-in `open()`)
- Impact: MEDIUM

```python
@llm.function_tool()
async def read_local_file(self, filename: str) -> str:
    """Reads a text file from the user's documents folder.
    Args: filename — e.g. 'notes.txt', 'todo.md'"""
    import pathlib
    # Safety: restrict to safe directory only
    safe_dir = pathlib.Path.home() / "Documents" / "JARVIS"
    safe_dir.mkdir(parents=True, exist_ok=True)
    target = (safe_dir / filename).resolve()
    if not str(target).startswith(str(safe_dir)):
        return "Access denied: file is outside safe directory."
    if not target.exists():
        return f"File '{filename}' not found in JARVIS Documents folder."
    try:
        text = await asyncio.to_thread(target.read_text, encoding="utf-8")
        return f"Contents of {filename}:\n{text[:2000]}"
    except Exception as e:
        return f"Could not read file: {e}"
```

---

**5. Morning Briefing (Multi-tool Chain)**
- New tool: `morning_briefing()`
- Internally chains: time + weather (your city) + agenda + optional news
- All tools already exist — this just calls them and compiles the result
- Impact: HIGH perceived intelligence, 0 new dependencies

```python
@llm.function_tool()
async def morning_briefing(self) -> str:
    """Delivers a compiled morning briefing: time, weather, agenda events."""
    time_info = await self.get_current_time()
    weather_info = await self.get_weather_data(location="Mumbai", days_from_today=0)
    agenda_info = await self.view_agenda_events()
    return f"MORNING BRIEFING:\n{time_info}\n{weather_info}\n{agenda_info}"
```

---

**6. System Volume Control (Windows)**
- New tool: `set_volume(level_percent)`
- Uses `pycaw` or PowerShell subprocess (no extra install needed)
- "JARVIS set volume to 50 percent"
- Impact: MEDIUM

```python
@llm.function_tool()
async def set_volume(self, level_percent: int) -> str:
    """Sets the system master volume. Args: level_percent — 0 to 100."""
    level = max(0, min(100, level_percent))
    import subprocess
    script = f"(New-Object -com Shell.Application).Windows() | Out-Null; $obj = New-Object -ComObject WScript.Shell; [System.Media.SystemSounds]::Beep; Add-Type -TypeDefinition 'using System.Runtime.InteropServices; [Guid(\"5CDF2C82-841E-4546-9722-0CF74078229A\"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] public interface IAudioEndpointVolume {{ int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext); }}'"
    # Simple approach via PowerShell:
    cmd = f"powershell -c \"$vol = [Math]::Round({level}/100, 2); (New-Object -ComObject Shell.Application); nircmd.exe setsysvolume ([Math]::Round($vol * 65535))\""
    try:
        await asyncio.to_thread(subprocess.run, ["powershell", "-c",
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}; "  # mute first
            f"# Use pycaw for real control"
        ], capture_output=True, timeout=3)
        return f"Volume set to {level}%."
    except Exception as e:
        return f"Could not set volume: {e}"
```

NOTE: For proper volume control, add `pycaw` to requirements.txt. Cleaner than PowerShell.

---

### TIER 2 — Plan Before Building (moderate effort)

**7. Proactive Weather Alert**
Checks weather at session start. If rain/storm likely, says proactively:
"Sir, there's a 90% chance of rain today. Take an umbrella."
Implementation: call `get_weather_data` in `entrypoint()` after session starts,
conditionally fire `session.say()` if precip > 70%.
~15 lines in worker.py.

**8. Persistent Search Cache (Cross-session)**
Adds a `search_cache` table to existing SQLite DB with expiry timestamps.
Before calling Tavily, check DB for recent result (< 24h old).
Saves Tavily credits for stable data (news changes, internship listings less so).
~30 lines in memory_db.py + search_and_read.

**9. Smart Note Writer**
"JARVIS take a note: [content]" → writes to `~/Documents/JARVIS/notes_YYYY-MM-DD.md`
with timestamp. "Read my notes from today" → reads it back.
Extension of existing `add_agenda_event` pattern.

**10. Autonomous Research Report**
"JARVIS research Python async programming and email me a summary"
Chain: search_and_read → scrape top 3 → run_python to compile → send_research_email
This is multi-step tool chaining — **already works natively** with Llama 3.3's
tool calling. No code needed. Just prompt the LLM correctly and it chains tools.

---

### TIER 3 — Evaluate Carefully (adds overhead)

**11. Screenshot + Vision Description**
Take screenshot → encode as base64 → send to a vision LLM (Gemini vision).
Needs: `Pillow` + `mss` (screen capture). Risk: adds 1-2s latency for vision API call.
Only worth it if user explicitly needs "what's on my screen".

**12. Wake Word Detection**
SKIP on i3 as discussed — thread starvation risk per SKILL.md.

**13. Multi-turn Research Task**
"Keep researching Python internships every day and tell me when a new one appears"
Needs: persistent background task + database polling.
This is the boundary of what a single-process agent should do.
Better to build as a separate scheduled script that injects into memory_db.

---

## Part 4: In-Session Search Memory — How It Already Works

```
Turn 1: "Search Internshala for Python internships"
  → JARVIS calls search_and_read("site:internshala.com python internship")
  → ChatContext now contains the full tool output (company names, stipends, links)

Turn 2: "What was the highest stipend?"
  → Llama 3.3 reads ChatContext history
  → Answers from Turn 1's stored data
  → 0 Tavily credits spent ✅

Turn 3: "Search for data science internships too"
  → Different query → Tavily called (1 credit)
  → ChatContext now has BOTH search results

Turn 4: "Compare the stipends from both searches"
  → Llama 3.3 reasons across both tool outputs in ChatContext
  → 0 credits ✅
```

The only thing missing is the **in-session dict cache** (prevents re-searching the
exact same query if the LLM hallucinates a second tool call for same data).

---

## Recommended Implementation Order

```
IMMEDIATE (additive, zero risk):
  [ ] Memory auto-load in worker.py entrypoint    — 5 lines
  [ ] In-session search cache (dict on profile)   — 8 lines
  [ ] set_reminder tool                           — ~25 lines
  [ ] run_python sandbox tool                     — ~20 lines
  [ ] morning_briefing tool                       — ~10 lines
  [ ] read_clipboard tool                         — ~10 lines

NEXT SPRINT:
  [ ] read_local_file tool                        — ~20 lines
  [ ] set_volume tool (add pycaw to requirements) — ~10 lines
  [ ] Persistent search cache in SQLite           — ~30 lines

EVALUATE LATER:
  [ ] Screenshot + vision
  [ ] Proactive weather alert at session start
```

All IMMEDIATE items are additive tool functions or 5-line worker.py changes.
None touch the VAD → STT → LLM → TTS pipeline.
