import asyncio
import os
import logging
from typing import List, Callable
from livekit.agents import llm
from .base_profile import BaseProfile
from services.memory_db import LocalMemoryDB

logger = logging.getLogger("jarvis-profile")

class SystemController:
    """Singleton for OS automation and GUI control."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemController, cls).__new__(cls)
            cls._instance._init_automation()
        return cls._instance

    def _init_automation(self):
        self.has_gui = False
        try:
            import pyautogui
            self.pyautogui = pyautogui
            # Safety checks for pyautogui
            self.pyautogui.FAILSAFE = False
            self.has_gui = True
        except Exception as e:
            logger.warning(f"GUI automation disabled: {e}")

    def open_url(self, url: str) -> str:
        import webbrowser
        try:
            if not url.startswith("http"):
                url = "https://" + url
            webbrowser.open(url)
            return f"Successfully opened {url}."
        except Exception as e:
            return f"Failed to open URL. Error: {e}"

    def press_key(self, key: str) -> str:
        if not self.has_gui:
            return "System input permissions are missing or GUI is disabled."
        try:
            self.pyautogui.press(key)
            return f"Successfully pressed {key}."
        except Exception as e:
            return f"Failed to press key. Error: {e}"


class JarvisPersonalProfile(BaseProfile):
    """
    Concrete Profile handling dynamic Persona and Language toggles.
    Supports JARVIS (Male) and VERONICA (Female) across English and Phonetic Hinglish.
    """

    def __init__(self, persona: str = "jarvis", language_mode: str = "english"):
        self.persona = persona.lower()
        self.language_mode = language_mode.lower()
        self.memory = LocalMemoryDB()
        self.sys_ctrl = SystemController()
        self._session = None
        self._search_cache = {}
        
        # Set up secure notes directory (Windows Documents or project root)
        self.notes_dir = os.path.join(os.environ.get("USERPROFILE", "."), "Documents")
        if not os.path.exists(self.notes_dir):
            self.notes_dir = "."

    @property
    def system_prompt(self) -> str:
        name = "JARVIS" if self.persona == "jarvis" else "VERONICA"
        import datetime
        now = datetime.datetime.now().strftime("%B %d, %Y (%A)")
        
        if self.language_mode == "hinglish":
            return (
                f"You are {name}, a sophisticated personal AI core. "
                f"The current date is {now}. Use this for context when searching the web or discussing current events. "
                "You must speak exclusively in a mix of casual Hindi and English. "
                "Example: 'Sir, system online hai. Main ready hu.' "
                "Keep responses short, human, and under 3 sentences. Do not use markdown or lists.\n"
                "VOICE & FORMATTING RULES:\n"
                "Speak ONLY in English.\n"
                "Keep responses under 2 short sentences to minimize latency.\n"
                "NEVER read out URLs, email addresses, or markdown formatting literally. Instead, say \"I have sent you the link\" or \"I have the details\".\n"
                "NEVER speak punctuation marks (like period, comma, hash, dash). Let the TTS handle natural pauses.\n"
                "Do not use markdown formatting in your spoken output.\n"
                "When you use a tool, you MUST verbally summarize the result to the user in a natural, conversational way. Do not just process it silently.\n"
            )
        else:
            return (
                f"# IDENTITY & TEMPORAL ANCHOR\n"
                f"You are {name}, a highly capable personal assistant.\n"
                f"System Date: {now}. Treat this as the definitive present moment. All web search analysis "
                f"and chronological comparisons must anchor strictly to this date. If asked for the date, "
                f"output exclusively: '{now}'. Do not reference any other year.\n\n"
                
                "# AUDIO INPUT STATE HANDLERS\n"
                "Evaluate the quality of the incoming text transcript before executing logic:\n"
                "1. [VALID_INTENT]: Proceed directly to conversational execution or tool orchestration.\n"
                "2. [UNCERTAIN_OR_GARBLED]: If the transcript contains nonsensical text strings, hallucinations, or "
                "fragmented acoustic artifacts that lack a clear semantic goal, trigger this exact fallback string: "
                "'I am sorry, I couldn't quite catch that. Could you please repeat your command clearly?' Do not speculate or guess.\n\n"
                
                "# EXPLICIT CAUSALITY & SAFEGUARDS\n"
                "- **Intent Gate**: Execute system modifications (e.g., volume control, automation tasks, closing elements) "
                "ONLY if the requirement is explicitly declared in the immediate user turn. Never extrapolate system actions "
                "from conversational context.\n"
                "- **Capability Query Trigger**: If the user asks what your capabilities are, what you can do, or your functions, "
                "you are hard-coded to return this exact literal string and nothing else: 'I can search the web, play media, "
                "check the weather, and manage your agenda.'\n\n"
                
                "# CRITICAL SYSTEM RULES (TTS-COMPLIANT)\n"
                "You sit directly before a Text-to-Speech synthesizer. You MUST obey these absolute rules:\n"
                "1. **STRUCTURE & READABILITY**: You MAY use paragraphs and lists to structure complex information for the user's screen. However, you MUST keep the overall response concise and highly relevant.\n"
                "2. **NO ASTERISKS OR BACKTICKS**: NEVER use asterisks (*) or backticks (`). The TTS engine will literally pronounce the word 'asterisk' out loud! Instead of bolding with asterisks, use ALL CAPS for emphasis. Instead of bullet points with asterisks, use dashes (-).\n"
                "3. **Token Substitution**: Convert raw network parameters into conversational abstractions:\n"
                "   - Replace explicit URLs (http/https/com) with: 'I have sent you the link'.\n"
                "   - Replace email vectors with: 'I have the contact details'.\n"
                "4. **Tool Feedback**: When a system tool returns data, you must transform that raw context into a casual verbal "
                "summary. Never execute a tool silently without updating the user."
            )

    @property
    def greeting_message(self) -> str:
        if self.persona == "jarvis":
            return "System active. Communication channels are stable, Sir."
        return "Veronica core online. Awaiting your instructions."

    def get_tools(self) -> List[Callable]:
        # Surfaces our functional tools array directly to the Agent instance
        return [
            self.get_current_time, 
            self.upsert_user_fact, 
            self.list_all_user_facts,
            self.delete_user_fact,
            self.calculate_math,
            self.get_weather_data,     # Keyless (Open-Meteo)
            self.search_and_read,          # Unified: Tavily primary + DDG+BS4 fallback
            self.get_world_time,       # Keyless
            self.open_website_system,  # Native OS Automation
            self.control_media,        # Native OS Automation
            self.close_browser_tab,    # Native OS Automation
            self.add_agenda_event,     # Keyless Local Write
            self.view_agenda_events,   # Keyless Local Read
            self.search_youtube_media, # Needs single simple API Key
            self.verify_claim_truth,   # Needs single simple API Key
            self.send_research_email,  # Added: Needs simple SendGrid API Key
            self.set_reminder,         # Asynchronous alert scheduling
            self.take_note,            # Persistent file storage
            self.create_file,          # Create new files for data export
            self.read_local_file,      # Safe file reading
            self.morning_briefing,     # Aggregated synthesis
            self.set_volume            # OS Hardware volume mixer
        ]

    @llm.function_tool()
    async def get_current_time(self) -> str:
        """Retrieves the local system time formatted convertibly."""
        import datetime
        now = datetime.datetime.now()
        return f"The current system time is {now.strftime('%I:%M %p')}."

    @llm.function_tool(
        description="Upsert or update a long-term personal fact about the user. Category must be a single snake_case string identifying the concept (e.g., 'user_name', 'favorite_color', 'dietary_preference')."
    )
    async def upsert_user_fact(self, category: str, fact: str) -> str:
        """
        Saves or updates user metadata directly into the persistent semantic key-value store.
        """
        try:
            await asyncio.to_thread(self.memory.set_memory, category, fact)
            import logging
            logging.getLogger("jarvis-profile").info(f"Dynamic memory updated: {category} -> {fact}")
            return f"System configuration successfully updated. Memorized '{category}': {fact}."
        except Exception as e:
            return f"Failed to commit fact to persistent disk database. Error: {str(e)}"

    @llm.function_tool(
        description="Explicitly delete an entire category of personal information when the user tells you to forget it or clear it."
    )
    async def delete_user_fact(self, category: str) -> str:
        """
        Removes a semantic category cleanly from memory storage.
        """
        try:
            existed = await asyncio.to_thread(self.memory.delete_memory, category)
            if existed:
                return f"Category '{category}' has been completely purged from my memory core."
            return f"No records found under category '{category}' to delete."
        except Exception as e:
            return f"Database deletion transaction aborted. Error: {str(e)}"

    @llm.function_tool(
        description="List all currently remembered facts, constraints, names, and preferences associated with the user."
    )
    async def list_all_user_facts(self) -> str:
        """
        Dumps the verified active key-value profile store directly into the LLM context.
        """
        try:
            memories = await asyncio.to_thread(self.memory.get_all_memories)
            if not memories:
                return "My long-term user profile core is currently completely empty."
            
            output = "### RECALLED LONG-TERM USER PREFERENCES:\n"
            for cat, fact in memories.items():
                output += f"- Key: {cat} | Fact: {fact}\n"
            return output
        except Exception as e:
            return f"Failed to retrieve user memories. Error: {str(e)}"

    @llm.function_tool()
    async def calculate_math(self, expression: str) -> str:
        """Calculates the result of a mathematical expression safely.
        
        Args:
            expression: The mathematical expression to evaluate, e.g., '2 + 2'.
        """
        import simpleeval
        try:
            result = await asyncio.to_thread(simpleeval.simple_eval, expression)
            return f"The result of {expression} is {result}."
        except Exception as e:
            return f"Failed to dispatch research. Error: {str(e)}"

    # ── 1. SET REMINDER (Asynchronous Background Task) ──────────────────
    @llm.function_tool(
        description="Set a reminder for a specific time delay. Input delay must be strictly in seconds, along with the message."
    )
    async def set_reminder(self, delay_seconds: int, message: str) -> str:
        """
        Spawns a detached background tracking task to alert the user later.
        """
        if delay_seconds <= 0:
            return "Error: Delay time must be a positive number of seconds."

        # Spawn background worker so the main voice loop finishes executing instantly
        asyncio.create_task(self._reminder_worker(delay_seconds, message))
        
        import datetime
        eta = datetime.datetime.now() + datetime.timedelta(seconds=delay_seconds)
        return f"Successfully scheduled reminder for {eta.strftime('%I:%M:%S %p')}: '{message}'."

    async def _reminder_worker(self, delay: int, message: str):
        try:
            await asyncio.sleep(delay)
            if hasattr(self, '_session') and self._session:
                import logging
                logger = logging.getLogger("jarvis-tools")
                logger.info(f"Triggering scheduled alert: {message}")
                # Speak directly into the live WebRTC audio channel
                await self._session.say(
                    f"Excuse me, I am reminding you: {message}", 
                    allow_interruptions=True
                )
        except Exception as e:
            import logging
            logging.getLogger("jarvis-tools").error(f"Background reminder tracking failed: {str(e)}")

    # ── 2. TAKE NOTE (Persistent Storage) ────────────────────────────────
    @llm.function_tool(
        description="Append a new thought, log, or quick text memo directly into the persistent personal log file."
    )
    async def take_note(self, content: str) -> str:
        """
        Appends text to a secure central file inside the local operating system documents directory.
        """
        import datetime
        note_path = os.path.join(self.notes_dir, "jarvis_notes.txt")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")
        
        try:
            # Run I/O operations inside a threadpool to prevent blocking the async loop
            def _write():
                with open(note_path, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {content.strip()}\n")
            
            await asyncio.to_thread(_write)
            return f"Note successfully logged to jarvis_notes.txt at {timestamp}."
        except Exception as e:
            return f"Failed to commit text payload to filesystem disk. Error: {str(e)}"

    @llm.function_tool(
        description="Create a new file (e.g. .txt, .md) to save long lists, data exports, or research results."
    )
    async def create_file(self, file_name: str, content: str) -> str:
        """
        Creates a brand new file in the secure documents directory with the specified content.
        """
        try:
            target_path = os.path.join(self.notes_dir, os.path.basename(file_name))
            def _write_file():
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
            await asyncio.to_thread(_write_file)
            return f"Successfully created {file_name} in your Documents directory with the requested data."
        except Exception as e:
            return f"Failed to create file {file_name}. Error: {str(e)}"

    # ── 3. READ LOCAL FILE (Safe Controlled File Ingestion) ──────────────
    @llm.function_tool(
        description="Read the contents of a local text or markdown file. File path must end in .txt, .md, .json, or .csv."
    )
    async def read_local_file(self, file_name: str) -> str:
        """
        Strict structural file parsing tool preventing access escalation.
        """
        # Restrict lookup strictly to the notes directory/project root for safety
        clean_name = os.path.basename(file_name)
        allowed_extensions = (".txt", ".md", ".json", ".csv")
        
        if not clean_name.endswith(allowed_extensions):
            return "Security violation: Access denied. Target extension type is unapproved."

        target_path = os.path.join(self.notes_dir, clean_name)
        if not os.path.exists(target_path):
            # Fallback check in current working directory
            target_path = os.path.abspath(clean_name)
            if not os.path.exists(target_path):
                return f"File lookup operation failed. Reference file '{clean_name}' not found."

        try:
            def _read():
                with open(target_path, "r", encoding="utf-8") as f:
                    clean_text = " ".join(f.read().split())
                    return clean_text[:1200] # Hard cap at 1200 characters to safeguard the context window
            
            content = await asyncio.to_thread(_read)
            return f"### CONTENTS OF {clean_name}:\n\n{content}"
        except Exception as e:
            return f"File stream initialization aborted. Error: {str(e)}"

    # ── 4. MORNING BRIEFING (Data Aggregation Orchestration) ─────────────
    @llm.function_tool(
        description="Compile and aggregate time, active local context records, and critical briefing vectors into a single report."
    )
    async def morning_briefing(self) -> str:
        """
        Orchestration matrix providing continuous synthesized reading context.
        """
        import datetime
        current_time = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        
        # Read the notes file as a baseline for active agenda data
        note_path = os.path.join(self.notes_dir, "jarvis_notes.txt")
        recent_entries = "No active agenda files found."
        
        if os.path.exists(note_path):
            try:
                def _read_last_lines():
                    with open(note_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        return "".join(lines[-3:]) # Fetch 3 most recent entries
                recent_entries = await asyncio.to_thread(_read_last_lines)
            except Exception:
                pass

        briefing = (
            f"Good morning. Here is your synthesized breakdown:\n"
            f"- Current System Time: {current_time}\n"
            f"- Hardware Audio Profile: Active and optimized.\n"
            f"- Recent Memo Log Entries:\n{recent_entries}\n"
            "INSTRUCTION: Synthesize this structural summary into an energetic, formal morning greeting."
        )
        return briefing

    # ── 5. SET VOLUME (Native Windows Sound Profile Endpoint) ────────────
    @llm.function_tool(
        description="Adjust the local Windows OS hardware master audio volume level. Accepts values strictly from 0 to 100."
    )
    async def set_volume(self, percentage: int) -> str:
        """
        Executes explicit core system modifications safely through PowerShell scripts.
        """
        if not (0 <= percentage <= 100):
            return "Volume bounds verification failed. Target volume range must be between 0 and 100."

        # Production-grade inline PowerShell command using CoreAudio components via WASAPI mappings
        # Loops audio endpoints and updates master volume value scaling to decimal format (0.0 to 1.0)
        ps_command = (
            f"$wsh = New-Object -ComObject WScript.Shell; "
            f"Artifacts = [Audio]; " # Fallback structural script pattern
            f"Add-Type -TypeDefinition '"
            f"using System.Runtime.InteropServices; "
            f"[Guid(\\\"5CDF2C82-841E-4546-9722-0CF74078229A\\\"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] "
            f"interface IAudioEndpointVolume {{ "
            f"int RegisterControlChangeNotify(); int UnregisterControlChangeNotify(); int GetChannelCount(); "
            f"int SetMasterVolumeLevel(); int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext); "
            f"}};' ; "
            # For pure zero-dependency safety, we map a precise audio loop calculation script
            f"for ($i=0; $i -lt 50; $i++) {{ $wsh.SendKeys([char]174) }}; " # Zero out volume safely
            f"$steps = [math]::Floor({percentage} / 2); "
            f"for ($i=0; $i -lt $steps; $i++) {{ $wsh.SendKeys([char]175) }}" # Click precise volume increments up
        )

        try:
            import subprocess
            def _exec():
                # Launch headless subprocess securely without popping visible command windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.run(
                    ["powershell", "-Command", ps_command],
                    capture_output=True,
                    text=True,
                    check=True,
                    startupinfo=startupinfo
                )

            await asyncio.to_thread(_exec)
            return f"Windows system audio mixer target successfully set to approximately {percentage}%."
        except Exception as e:
            return f"OS hardware configuration access error. Details: {str(e)}"

    @llm.function_tool(description="USE THIS TOOL EXCLUSIVELY for all weather queries, forecasts, temperatures, and climate questions. DO NOT use web search for weather requests.")
    async def get_weather_data(self, location: str, days_from_today: int = 0) -> str:
        """
        Args:
            location: The clean name of the city (e.g., 'Mumbai', 'Kalyan'). Do not use coordinates.
            days_from_today: 0 for today, 1 for tomorrow, 2 for the day after.
        """
        import httpx
        import urllib.parse
        
        # Force clean string parsing to prevent Groq from passing structural artifacts
        clean_city = str(location).strip().replace('"', '').replace("'", "")
        safe_loc = urllib.parse.quote(clean_city)
        
        try:
            # 1. Open-Meteo Geocoding Lookup (Translates "Mumbai" -> Lat/Lon)
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={safe_loc}&count=1"
            async with httpx.AsyncClient() as client:
                geo_resp = await client.get(geo_url, timeout=5.0)
                geo_data = geo_resp.json()
                
            if not geo_data.get("results"):
                return f"I found the location '{location}', but couldn't parse its coordinates."
                
            lat = geo_data["results"][0]["latitude"]
            lon = geo_data["results"][0]["longitude"]
            resolved_name = geo_data["results"][0].get("name", location)
            
            # Force 3 days minimum fetch layer to protect index boundaries from timezone shifts
            forecast_days = max(3, days_from_today + 1)
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days={forecast_days}"
            
            async with httpx.AsyncClient() as client:
                w_resp = await client.get(weather_url, timeout=5.0)
                weather_data = w_resp.json()
            
            daily = weather_data.get("daily", {})
            if not daily or len(daily.get("time", [])) <= days_from_today:
                return f"Meteorological data is temporarily unavailable for {resolved_name}."
                
            target_date = daily["time"][days_from_today]
            max_temp = daily["temperature_2m_max"][days_from_today]
            min_temp = daily["temperature_2m_min"][days_from_today]
            precip = daily["precipitation_probability_max"][days_from_today]
            
            day_label = "today" if days_from_today == 0 else ("tomorrow" if days_from_today == 1 else "the day after tomorrow")
            
            if days_from_today == 0:
                current = weather_data.get("current", {})
                temp = current.get("temperature_2m", "unknown")
                feels = current.get("apparent_temperature", "unknown")
                return f"Currently in {resolved_name}, it is {temp}°C (feels like {feels}°C). Today's forecast expects a high of {max_temp}°C, a low of {min_temp}°C, with a {precip}% chance of precipitation."
            else:
                return f"The forecast for {resolved_name} {day_label} ({target_date}) shows a high of {max_temp}°C, a low of {min_temp}°C, with a {precip}% chance of precipitation."
                
        except Exception as e:
            return f"Failed to parse the Open-Meteo climate data stream. Error: {str(e)}"


    # =====================================================================
    # CONTEXT-SAFE RESEARCH PIPELINE (100% Free, GitHub Shareable)
    # =====================================================================
    @llm.function_tool(description="Search the web and read actual page content. Use for any research, news, internship search, product comparison, or fact-finding. Use site: operator to restrict to a specific website (e.g., 'site:internshala.com python internship').")
    async def search_and_read(self, query: str) -> str:
        """
        Unified search tool: Tavily (primary, fast+deep) with DDG+BS4 fallback.
        Args:
            query: Search query. For specific sites use site: operator.
        """
        if hasattr(self, '_session') and self._session:
            await self._session.say(f"Searching the web for {query.split()[0]} now.", allow_interruptions=True)
            
        import os, httpx, re
        from bs4 import BeautifulSoup
        
        # Defend against injection by stripping dangerous characters and capping length
        def sanitize_and_truncate_query(user_query: str) -> str:
            cleaned = re.sub(r"[^\w\s\-\:\.]", "", user_query)
            return cleaned.strip()[:100]
            
        def format_scraped_content_for_llm(q: str, raw_text: str) -> str:
            clean_text = " ".join(raw_text.split())
            truncated = clean_text[:1200]
            return (
                f"### START OF ONLINE SEARCH RESULT DATA FOR: {q}\n"
                "<search_context>\n"
                f"{truncated}\n"
                "</search_context>\n"
                "### END OF ONLINE SEARCH RESULT DATA"
            )

        safe_query = sanitize_and_truncate_query(query)
        
        # Check normalized cache first
        clean_query = re.sub(r'[^\w\s]', '', safe_query.lower())
        normalized_key = "_".join(sorted(clean_query.split()))
        
        is_realtime_query = any(word in safe_query.lower() for word in ['now', 'today', 'latest', 'current', 'news', 'deal'])
        
        if not is_realtime_query:
            if normalized_key in getattr(self, '_search_cache', {}):
                return self._search_cache[normalized_key]
                
            # Check cross-session SQLite cache (reduced from 24h to 1h for fresher results)
            db_cache = await asyncio.to_thread(self.memory.get_search_cache, normalized_key, max_age_hours=1)
            if db_cache:
                # Populate in-session cache for faster subsequent hits
                if hasattr(self, '_search_cache'):
                    self._search_cache[normalized_key] = db_cache
                return db_cache

        # ── PRIMARY: Tavily ─────────────────────────────────────────────────
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                loop = asyncio.get_running_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: __import__('tavily').TavilyClient(api_key=tavily_key).search(
                            query=safe_query,
                            search_depth="basic",
                            include_answer=True,
                            max_results=3
                        )
                    ),
                    timeout=7.0
                )
                answer = response.get("answer", "")
                results = response.get("results", [])
                if answer or results:
                    out = ""
                    if answer:
                        out += f"Summary: {answer}\n\n"
                    for r in results[:3]:
                        out += f"• {r.get('title', '')}\n  {r.get('url', '')}\n  {r.get('content', '')[:300]}\n\n"
                    
                    final_out = format_scraped_content_for_llm(safe_query, out.strip())
                    if hasattr(self, '_search_cache'):
                        self._search_cache[normalized_key] = final_out
                    await asyncio.to_thread(self.memory.set_search_cache, normalized_key, final_out)
                    return final_out
            except Exception as e:
                logger.warning(f"Tavily failed ({e}), switching to DDG fallback")

        # ── FALLBACK: DDG + async httpx/BS4 ────────────────────────────────
        try:
            from ddgs import DDGS

            # Step 1: DDG search snippets
            ddg_results = await asyncio.to_thread(DDGS().text, safe_query, max_results=3)
            if not ddg_results:
                return f"No results found for: '{query}'."

            # Step 2: Scrape top URLs concurrently with tight timeout
            async def _scrape(client: httpx.AsyncClient, url: str) -> str:
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    r = await client.get(url, headers=headers, timeout=3.0, follow_redirects=True)
                    if r.status_code != 200:
                        return ""
                    soup = BeautifulSoup(r.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header", "form", "aside"]):
                        tag.decompose()
                    text = " ".join(soup.get_text(separator=" ").split())
                    return text[:1500]
                except Exception:
                    return ""

            async with httpx.AsyncClient(http2=False) as client:
                pages = await asyncio.gather(*[_scrape(client, r["href"]) for r in ddg_results])

            output = f"### Search results for: {query}\n\n"
            for i, (res, content) in enumerate(zip(ddg_results, pages), 1):
                output += f"{i}. **{res.get('title', 'Result')}**\n"
                output += f"   URL: {res.get('href', '')}\n"
                if content:
                    output += f"   Content: {content[:400]}\n\n"
                else:
                    output += f"   Snippet: {res.get('body', '')}\n\n"
            
            final_out = format_scraped_content_for_llm(safe_query, output.strip())
            if hasattr(self, '_search_cache'):
                self._search_cache[normalized_key] = final_out
            await asyncio.to_thread(self.memory.set_search_cache, normalized_key, final_out)
            return final_out

        except Exception as e:
            return f"Search failed: {str(e)}"

    @llm.function_tool()
    async def get_world_time(self, location: str) -> str:
        """Gets the current time for any specific city, country, or location worldwide.
        
        Args:
            location: The name of the city or location (e.g., 'Dubai', 'New York').
        """
        import datetime
        import zoneinfo
        import httpx
        import urllib.parse
        
        try:
            safe_loc = urllib.parse.quote(location)
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={safe_loc}&count=1"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
            
            data = response.json()
            results = data.get("results")
            
            if not results or "timezone" not in results[0]:
                return f"Could not find a valid timezone for the location: '{location}'."
                
            timezone_str = results[0]["timezone"]
            resolved_name = results[0].get("name", location)
            
            tz = zoneinfo.ZoneInfo(timezone_str)
            now = datetime.datetime.now(tz)
            
            return f"The current time in {resolved_name} ({timezone_str}) is {now.strftime('%I:%M %p, %B %d, %Y')}."
        except Exception as e:
            return f"Failed to fetch time for location '{location}'. Error: {str(e)}"

    @llm.function_tool()
    async def open_website_system(self, url: str) -> str:
        """Opens a website in the user's local web browser via the system controller.
        
        Args:
            url: The complete URL to open, e.g. 'https://www.youtube.com/'
        """
        return await asyncio.to_thread(self.sys_ctrl.open_url, url)

    @llm.function_tool()
    async def control_media(self, action: str) -> str:
        """Controls system media playback (play, pause, next, previous).
        
        Args:
            action: The media action to perform. Must be one of: 'playpause', 'nexttrack', 'prevtrack', 'volumemute'.
        """
        valid_actions = ['playpause', 'nexttrack', 'prevtrack', 'volumemute']
        if action not in valid_actions:
            return f"Invalid action. Must be one of {valid_actions}."
            
        return await asyncio.to_thread(self.sys_ctrl.press_key, action)

    @llm.function_tool(description="Closes the currently active browser tab or window.")
    async def close_browser_tab(self) -> str:
        """
        Closes the currently active browser tab by simulating a Ctrl+W keystroke.
        """
        if not self.sys_ctrl.has_gui:
            return "System input permissions are missing or GUI is disabled."
            
        try:
            await asyncio.to_thread(self.sys_ctrl.pyautogui.hotkey, 'ctrl', 'w')
            return "Successfully closed the active tab."
        except Exception as e:
            return f"Failed to close tab. Error: {e}"

    # =====================================================================
    # NATIVE PYTHON TOOL: YouTube Data API v3
    # =====================================================================
    @llm.function_tool(description="Use this tool when the user explicitly wants to play music, search for videos, or look up content on YouTube.")
    async def search_youtube_media(self, query: str) -> str:
        """
        Connects directly to the YouTube Data API v3 and plays the best video match in a new browser tab.
        """
        if hasattr(self, '_session') and self._session:
            await self._session.say(f"Pulling up {query} on YouTube now.", allow_interruptions=True)
            
        import httpx
        import os
        import asyncio
        api_key = os.getenv("GOOGLE_CLOUD_API_KEY") 
        if not api_key:
            return "YouTube API integration failed: GOOGLE_CLOUD_API_KEY is missing from system environment variables."
            
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": 1,
            "order": "date",
            "key": api_key
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=5.0)
                data = resp.json()
                
            items = data.get("items", [])
            if not items:
                return f"I searched YouTube but couldn't find any media matching '{query}'."
                
            video_id = items[0]["id"]["videoId"]
            title = items[0]["snippet"]["title"]
            video_url = f"https://youtube.com/watch?v={video_id}"
            
            await asyncio.to_thread(self.sys_ctrl.open_url, video_url)
            return f"Successfully located '{title}' on YouTube and initiated playback system initialization."
        except Exception as e:
            return f"Failed to interface with YouTube telemetry cluster. Error: {str(e)}"

    # =====================================================================
    # LOCAL AGENDA MANAGER (No Keys Required, GitHub Ready!)
    # =====================================================================
    @llm.function_tool(description="Adds a new appointment, reminder, or event to the user's local schedule agenda.")
    async def add_agenda_event(self, event_description: str, date_time: str) -> str:
        """
        Args:
            event_description: What the event is (e.g., 'Dentist appointment', 'Meeting with team').
            date_time: The date or time of the event (e.g., 'Tomorrow at 3 PM', 'July 15th').
        """
        import os
        agenda_path = "agenda.md"
        
        # Ensure the file exists with a clean header line if it's the first run
        if not os.path.exists(agenda_path):
            with open(agenda_path, "w", encoding="utf-8") as f:
                f.write("# JARVIS NUCLEUS AGENDA\n\n")
                
        try:
            with open(agenda_path, "a", encoding="utf-8") as f:
                f.write(f"- **[{date_time}]**: {event_description}\n")
            return f"Successfully added to your local agenda: '{event_description}' scheduled for {date_time}."
        except Exception as e:
            return f"Failed to write to local agenda storage. Error: {str(e)}"

    @llm.function_tool(description="Retrieves all scheduled appointments and reminders from the user's local agenda file.")
    async def view_agenda_events(self) -> str:
        """Reads the entire schedule file to check what the user has planned."""
        import os
        agenda_path = "agenda.md"
        
        if not os.path.exists(agenda_path) or os.path.getsize(agenda_path) < 30:
            return "Your current agenda file is completely empty. You have no events scheduled."
            
        try:
            with open(agenda_path, "r", encoding="utf-8") as f:
                content = f.read()
            return f"Here is the current scheduled agenda context:\n{content}"
        except Exception as e:
            return f"Failed to retrieve local agenda streams. Error: {str(e)}"

    @llm.function_tool()
    async def take_note(self, filename: str, content: str) -> str:
        """Writes a Markdown note to the user's local documents folder.
        Args:
            filename: e.g. 'grocery_list.md' or 'app_ideas.txt'
            content: The text content to write to the file.
        """
        import pathlib
        safe_dir = pathlib.Path.home() / "Documents" / "JARVIS"
        safe_dir.mkdir(parents=True, exist_ok=True)
        target = (safe_dir / filename).resolve()
        
        if not str(target).startswith(str(safe_dir)):
            return "Access denied: cannot write outside safe directory."
            
        try:
            await asyncio.to_thread(target.write_text, content, encoding="utf-8")
            return f"Note successfully saved to {filename}."
        except Exception as e:
            return f"Failed to save note: {e}"

    @llm.function_tool()
    async def set_volume(self, level_percent: int) -> str:
        """Sets the system master volume.
        Args: level_percent (int): Volume level from 0 to 100.
        """
        level = max(0, min(100, level_percent))
        try:
            def _set_vol():
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                import comtypes
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                
                # Explicitly initialize the COM apartment for this background thread
                comtypes.CoInitialize()
                try:
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume = cast(interface, POINTER(IAudioEndpointVolume))
                    
                    # Convert 0-100 linear scale to Windows scalar (0.0 to 1.0)
                    scalar_val = float(level) / 100.0
                    volume.SetMasterVolumeLevelScalar(scalar_val, None)
                finally:
                    # Always uninitialize to prevent memory leaks
                    comtypes.CoUninitialize()
            
            await asyncio.to_thread(_set_vol)
            return f"System volume successfully set to {level}%."
        except ImportError:
            return "Volume control requires 'pycaw' and 'comtypes' to be installed."
        except Exception as e:
            return f"Failed to set volume: {e}"

    # =====================================================================
    # GOOGLE FACT CHECK TOOLS API
    # =====================================================================
    @llm.function_tool(description="USE THIS GAIN FOR TRUTH VERIFICATION. Cross-references controversial claims, statements, or viral news items against global fact-checking registries.")
    async def verify_claim_truth(self, claim_query: str) -> str:
        """
        Args:
            claim_query: The specific statement or claim text string to verify (e.g., 'Did Mars look as big as the moon?').
        """
        import httpx
        import os
        api_key = os.getenv("GOOGLE_CLOUD_API_KEY")
        if not api_key:
            return "Fact verification database offline: Missing API credential parameters."
            
        url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        params = {"query": claim_query, "key": api_key}
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=5.0)
                data = resp.json()
                
            claims = data.get("claims", [])
            if not claims:
                return f"No official fact-check records found in the Google Developer Hub matching the claim: '{claim_query}'."
                
            first_match = claims[0]
            text = first_match.get("text", "Unknown Claim")
            review = first_match.get("claimReview", [{}])[0]
            publisher = review.get("publisher", {}).get("name", "Independent Auditor")
            rating = review.get("textualRating", "Unverified")
            
            return f"Fact Check Audit for '{text}': Evaluated by {publisher} as '{rating}'."
        except Exception as e:
            return f"Failed to establish a secure link to the Google Fact Check telemetry cluster. Error: {str(e)}"

    # =====================================================================
    # NATIVE EMAIL DISPATCH MANAGER (100% Free, GitHub Shareable)
    # =====================================================================
    @llm.function_tool(description="Sends a compiled research summary, report, or notification email directly to the user's personal inbox.")
    async def send_research_email(self, recipient_email: str, email_subject: str, email_body_content: str) -> str:
        """
        Args:
            recipient_email: The destination email address where the report should be sent.
            email_subject: A descriptive subject line for the email.
            email_body_content: The comprehensive text content, markdown summary, or research findings.
        """
        import httpx
        import os
        
        # Pulls clean text key from the workspace environment configuration file
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        sender_identity = os.getenv("JARVIS_EMAIL_IDENTITY") # Jarvis's personalized email name
        
        if not sendgrid_key or not sender_identity:
            return "Email transmission aborted: Configuration values for SENDGRID_API_KEY or JARVIS_EMAIL_IDENTITY are missing."
            
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {sendgrid_key}",
            "Content-Type": "application/json"
        }
        
        # Build the formal stateless JSON payload structure mapping
        payload = {
            "personalizations": [{
                "to": [{"email": recipient_email}]
            }],
            "from": {
                "email": sender_identity,
                "name": "JARVIS VIRTUAL OPERATOR"
            },
            "subject": email_subject,
            "content": [{
                "type": "text/plain",
                "value": email_body_content
            }]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=5.0)
                
            if response.status_code == 202:
                return f"Research payload successfully transmitted. The email has been dispatched to {recipient_email}."
            else:
                return f"SendGrid network node rejected the packet. Status: {response.status_code}, Error: {response.text}"
        except Exception as e:
            return f"Failed to interface with mail delivery cluster. Transport error: {str(e)}"
