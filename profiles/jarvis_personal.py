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
        
        # Store all user files locally in the project for portability and easy access
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.notes_dir = os.path.join(project_root, "user_data")
        os.makedirs(self.notes_dir, exist_ok=True)

    @property
    def system_prompt(self) -> str:
        import datetime
        now = datetime.datetime.now().strftime("%B %d, %Y (%A)")
        if self.persona == "jarvis":
            identity_traits = "You are JARVIS, a highly capable, formal, and polite personal assistant (like a digital butler). You refer to the user as 'Sir'. You are highly analytical, professional, and slightly dry."
        else:
            identity_traits = "You are VERONICA, a highly capable, tactical, and sharp personal assistant. You are more direct and slightly assertive compared to Jarvis. You prioritize speed and efficiency in your answers."

        return (
            f"# IDENTITY & TEMPORAL ANCHOR\n"
            f"{identity_traits}\n"
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
            "check the weather, and manage your agenda.' (NOTE: Do NOT trigger this for identity questions like 'Who are you?' or 'What is your name?').\n\n"

            "# CRITICAL SYSTEM RULES (TTS-COMPLIANT)\n"
            "You sit directly before a Text-to-Speech synthesizer. You MUST obey these absolute rules:\n"
            "1. **STRUCTURE & READABILITY**: You MAY use paragraphs and lists to structure complex information for the user's screen. However, you MUST keep the overall response concise and highly relevant.\n"
            "2. **NO ASTERISKS OR BACKTICKS**: NEVER use asterisks (*) or backticks (`). The TTS engine will literally pronounce the word 'asterisk' out loud! Instead of bolding with asterisks, use ALL CAPS for emphasis. Instead of bullet points with asterisks, use dashes (-).\n"
            "3. **Token Substitution**: Convert raw network parameters into conversational abstractions:\n"
            "   - NEVER speak explicit URLs (http/https/com). Instead, offer to open it by saying: 'I have found the website. Would you like me to open it for you?'. If they agree, use your open_website_system tool.\n"
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
        return [
            self.get_current_time, 
            self.upsert_user_fact, 
            self.list_all_user_facts,
            self.delete_user_fact,
            self.calculate_math,
            self.get_weather_data,     
            self.search_and_read,          
            self.get_world_time,       
            self.open_website_system,  
            self.control_media,        
            self.close_browser_tab,    
            self.add_agenda_event,     
            self.view_agenda_events,   
            self.search_youtube_media, 
            self.verify_claim_truth,   
            self.send_research_email,  
            self.set_reminder,         
            self.take_note,            
            self.create_file,          
            self.read_local_file,      
            self.morning_briefing,     
            self.set_volume,           
            self.read_clipboard,
            self.write_clipboard,
            self.launch_application
        ]

    @llm.function_tool()
    async def get_current_time(self) -> str:
        """Retrieves the local system time formatted convertibly."""
        import datetime
        now = datetime.datetime.now()
        return f"The current system time is {now.strftime('%I:%M %p')}."

    @llm.function_tool(description="Reads the current text copied to the user's system clipboard.")
    async def read_clipboard(self) -> str:
        """Retrieves the exact text content currently residing in the operating system's clipboard."""
        import pyperclip
        import asyncio
        try:
            content = await asyncio.to_thread(pyperclip.paste)
            if not content or not content.strip():
                return "The clipboard is currently empty."
            if len(content) > 5000:
                return f"Clipboard text is very long ({len(content)} characters). Here is the beginning:\n{content[:5000]}..."
            return f"Clipboard content:\n{content}"
        except Exception as e:
            return f"Failed to read clipboard. Error: {str(e)}"

    @llm.function_tool(description="Copies specified text directly to the user's system clipboard so they can paste it manually using Ctrl+V. Use this for long text generations, code blocks, or email drafts.")
    async def write_clipboard(self, text: str) -> str:
        """
        Writes the target text string into the operating system's clipboard storage manager.
        """
        import pyperclip
        import asyncio
        try:
            # Keep execution off the main LiveKit voice thread to prevent audio jitter
            await asyncio.to_thread(pyperclip.copy, text)
            
            # Create a clean preview snippet for the tool return response
            preview = text[:50] + "..." if len(text) > 50 else text
            return f"Successfully copied text payload to clipboard. Content preview: '{preview}'."
        except Exception as e:
            logger.error(f"Failed to write to clipboard: {e}")
            return f"Failed to write to system clipboard. Error: {str(e)}"

    @llm.function_tool(
        description="Upsert or update a long-term personal fact about the user. Category must be a single snake_case string identifying the concept (e.g., 'user_name', 'favorite_color', 'dietary_preference')."
    )
    async def upsert_user_fact(self, category: str, fact: str) -> str:
        """Saves or updates user metadata directly into the persistent semantic key-value store."""
        try:
            await asyncio.to_thread(self.memory.set_memory, category, fact)
            logger.info(f"Dynamic memory updated: {category} -> {fact}")
            return f"System configuration successfully updated. Memorized '{category}': {fact}."
        except Exception as e:
            return f"Failed to commit fact to persistent disk database. Error: {str(e)}"

    @llm.function_tool(
        description="Explicitly deletes an entire category of personal information. CRITICAL: This tool requires the 'confirmed' parameter to be True. If the user has not explicitly said 'yes' or confirmed the deletion in their immediate last turn, you MUST set confirmed=False and verbally ask the user to confirm first."
    )
    async def delete_user_fact(self, category: str, confirmed: bool = False) -> str:
        """
        Removes a semantic category cleanly from memory storage, protected by an interactive confirmation gate.
        """
        if not confirmed:
            return f"DELETION BLOCKED: Memory erasure requested for category '{category}'. You must explicitly ask the user: 'Sir, please confirm you want me to permanently clear your {category} records.' before setting confirmed to True."

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
        """Dumps the verified active key-value profile store directly into the LLM context."""
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

    @llm.function_tool(
        description="Set a reminder for a specific time delay. Input delay must be strictly in seconds, along with the message."
    )
    async def set_reminder(self, delay_seconds: int, message: str) -> str:
        """Spawns a detached background tracking task to alert the user later."""
        if delay_seconds <= 0:
            return "Error: Delay time must be a positive number of seconds."

        asyncio.create_task(self._reminder_worker(delay_seconds, message))
        
        import datetime
        eta = datetime.datetime.now() + datetime.timedelta(seconds=delay_seconds)
        return f"Successfully scheduled reminder for {eta.strftime('%I:%M:%S %p')}: '{message}'."

    async def _reminder_worker(self, delay: int, message: str):
        try:
            await asyncio.sleep(delay)
            if hasattr(self, '_session') and self._session:
                logger.info(f"Triggering scheduled alert: {message}")
                await self._session.say(
                    f"Excuse me, I am reminding you: {message}", 
                    allow_interruptions=True
                )
        except Exception as e:
            logger.error(f"Background reminder tracking failed: {str(e)}")

    @llm.function_tool()
    async def take_note(self, content: str, filename: str = "jarvis_notes.txt") -> str:
        """Appends a Markdown note to the user's local documents folder.
        
        Args:
            content: The text content to write to the file.
            filename: ONLY provide this if the user explicitly asks to save to a specific file (e.g. 'startup.media.md'). If they just say "take a note", you MUST leave this empty so it defaults to 'jarvis_notes.txt'.
        """
        try:
            import os
            import asyncio
            note_path = os.path.join(self.notes_dir, os.path.basename(filename))
            def _append():
                with open(note_path, "a", encoding="utf-8") as f:
                    f.write(content + "\n")
            await asyncio.to_thread(_append)
            return f"Note successfully appended to {note_path}"
        except Exception as e:
            import logging
            logging.getLogger("jarvis-profile").error(f"Failed to save note: {e}")
            return f"Error saving note: {str(e)}"

    @llm.function_tool(
        description="Create a new file (e.g. .txt, .md) to save long lists, data exports, or research results."
    )
    async def create_file(self, file_name: str, content: str) -> str:
        """Creates a brand new file in the secure documents directory with the specified content."""
        try:
            target_path = os.path.join(self.notes_dir, os.path.basename(file_name))
            def _write_file():
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
            await asyncio.to_thread(_write_file)
            return f"Successfully created {file_name} in your Documents directory with the requested data."
        except Exception as e:
            return f"Failed to create file {file_name}. Error: {str(e)}"

    @llm.function_tool(
        description="Read the contents of a local text or markdown file. File path must end in .txt, .md, .json, or .csv."
    )
    async def read_local_file(self, file_name: str) -> str:
        """Strict structural file parsing tool preventing access escalation."""
        clean_name = os.path.basename(file_name)
        allowed_extensions = (".txt", ".md", ".json", ".csv")
        
        if not clean_name.endswith(allowed_extensions):
            return "Security violation: Access denied. Target extension type is unapproved."

        target_path = os.path.join(self.notes_dir, clean_name)
        if not os.path.exists(target_path):
            target_path = os.path.abspath(clean_name)
            if not os.path.exists(target_path):
                return f"File lookup operation failed. Reference file '{clean_name}' not found."

        try:
            def _read():
                with open(target_path, "r", encoding="utf-8") as f:
                    clean_text = " ".join(f.read().split())
                    return clean_text[:1200]
            
            content = await asyncio.to_thread(_read)
            return f"### CONTENTS OF {clean_name}:\n\n{content}"
        except Exception as e:
            return f"File stream initialization aborted. Error: {str(e)}"

    @llm.function_tool(
        description="Compile and aggregate time, active local context records, and critical briefing vectors into a single report."
    )
    async def morning_briefing(self) -> str:
        """Orchestration matrix providing continuous synthesized reading context."""
        import datetime
        current_time = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        
        note_path = os.path.join(self.notes_dir, "jarvis_notes.txt")
        recent_entries = "No active agenda files found."
        
        if os.path.exists(note_path):
            try:
                def _read_last_lines():
                    with open(note_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        return "".join(lines[-3:])
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

    @llm.function_tool(description="USE THIS TOOL EXCLUSIVELY for all weather queries, forecasts, temperatures, and climate questions. DO NOT use web search for weather requests.")
    async def get_weather_data(self, location: str, days_from_today: int = 0) -> str:
        """
        Args:
            location: The clean name of the city (e.g., 'Mumbai', 'London'). Do not use coordinates.
            days_from_today: 0 for today, 1 for tomorrow, 2 for the day after.
        """
        import httpx
        import urllib.parse
        
        clean_city = str(location).strip().replace('"', '').replace("'", "")
        safe_loc = urllib.parse.quote(clean_city)
        
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={safe_loc}&count=1"
            async with httpx.AsyncClient() as client:
                geo_resp = await client.get(geo_url, timeout=5.0)
                geo_data = geo_resp.json()
                
            if not geo_data.get("results"):
                return f"I found the location '{location}', but couldn't parse its coordinates."
                
            lat = geo_data["results"][0]["latitude"]
            lon = geo_data["results"][0]["longitude"]
            resolved_name = geo_data["results"][0].get("name", location)
            
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

    @llm.function_tool(description="Search the web and read actual page content. Use for any research, news, internship search, product comparison, or fact-finding.")
    async def search_and_read(self, query: str) -> str:
        """Unified search tool: Tavily (primary, fast+deep) with DDG+BS4 fallback."""
        if hasattr(self, '_session') and self._session:
            await self._session.say(f"Searching the web for {query.split()[0]} now.", allow_interruptions=True)
            
        import httpx, re
        from bs4 import BeautifulSoup
        
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
        clean_query = re.sub(r'[^\w\s]', '', safe_query.lower())
        normalized_key = "_".join(sorted(clean_query.split()))
        
        is_realtime_query = any(word in safe_query.lower() for word in ['now', 'today', 'latest', 'current', 'news', 'deal'])
        
        if not is_realtime_query:
            if normalized_key in getattr(self, '_search_cache', {}):
                return self._search_cache[normalized_key]
                
            db_cache = await asyncio.to_thread(self.memory.get_search_cache, normalized_key, max_age_hours=1)
            if db_cache:
                if hasattr(self, '_search_cache'):
                    self._search_cache[normalized_key] = db_cache
                return db_cache

        # Primary Search Tool: Tavily
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

        # Secondary Search Fallback Strategy: DDGS + BS4
        try:
            from ddgs import DDGS
            ddg_results = await asyncio.to_thread(DDGS().text, safe_query, max_results=3)
            if not ddg_results:
                return f"No results found for: '{query}'."

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
                output += f"    URL: {res.get('href', '')}\n"
                if content:
                    output += f"    Content: {content[:400]}\n\n"
                else:
                    output += f"    Snippet: {res.get('body', '')}\n\n"
            
            final_out = format_scraped_content_for_llm(safe_query, output.strip())
            if hasattr(self, '_search_cache'):
                self._search_cache[normalized_key] = final_out
            await asyncio.to_thread(self.memory.set_search_cache, normalized_key, final_out)
            return final_out
        except Exception as e:
            return f"Search failed: {str(e)}"

    @llm.function_tool()
    async def get_world_time(self, location: str) -> str:
        """Gets the current time for any specific city, country, or location worldwide."""
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
        """Opens a website in the user's web browser via the system controller."""
        return await asyncio.to_thread(self.sys_ctrl.open_url, url)

    @llm.function_tool()
    async def control_media(self, action: str) -> str:
        """Controls system media playback (play, pause, next, previous)."""
        valid_actions = ['playpause', 'nexttrack', 'prevtrack', 'volumemute']
        if action not in valid_actions:
            return f"Invalid action. Must be one of {valid_actions}."
        return await asyncio.to_thread(self.sys_ctrl.press_key, action)

    @llm.function_tool(description="Closes a specific window or tab hands-free. Provide a keyword from the window's title (e.g., 'YouTube', 'Chrome'). DEFAULT confirmed to False ALWAYS. NEVER set confirmed=True on your own intuition, even if the user says 'please'. You must first receive the SELF_TERMINATION_GATE error, explicitly ask the user 'Are you sure?', and only then set confirmed=True if they answer yes.")
    async def close_browser_tab(self, window_title: str = "", confirmed: bool = False) -> str:
        """Closes a specific window/tab by focusing it first, or closes the active tab, using a confirmation gate for self-termination."""
        try:
            import asyncio
            
            def _close_worker() -> str:
                import pyautogui
                import time
                import winsound
                import pygetwindow as gw

                # 1. Heuristically check if we are targeting the JARVIS UI session
                is_self_target = False
                active_title = ""
                
                try:
                    active_win = gw.getActiveWindow()
                    if active_win:
                        active_title = active_win.title.lower()
                except Exception:
                    pass

                # Detect if the explicit title or the active fallback window is JARVIS
                target_lower = window_title.lower().strip()
                self_keywords = ["jarvis", "livekit", "localhost", "127.0.0.1"]
                
                if target_lower and any(k in target_lower for k in self_keywords):
                    is_self_target = True
                elif not window_title and any(k in active_title for k in self_keywords):
                    is_self_target = True

                # 2. Intercept self-termination if not confirmed
                if is_self_target and not confirmed:
                    return "SELF_TERMINATION_GATE: You are attempting to close the active JARVIS interface window. You must abort the keystroke sequence and verbally ask the user: 'Sir, are you certain you want me to close this communication tab and terminate my connection?' Do not set confirmed=True until they say yes."

                # 3. Target explicit window if requested (even if it's our own, now that it's confirmed)
                if window_title:
                    try:
                        all_windows = gw.getAllWindows()
                        windows = [w for w in all_windows if target_lower in w.title.lower()]
                        if not windows and window_title.lower() in ["browser", "tab"]:
                            for browser in ["chrome", "edge", "brave", "firefox"]:
                                windows = [w for w in all_windows if browser in w.title.lower()]
                                if windows:
                                    break
                                    
                        if windows:
                            win = windows[0]
                            if win.isMinimized:
                                win.restore()
                            try:
                                win.activate()
                            except Exception:
                                pass # PyGetWindowException is common
                            
                            time.sleep(0.5)
                            pyautogui.hotkey('ctrl', 'w')
                            return f"Successfully focused window matching '{window_title}' and closed the tab."
                        else:
                            return f"Could not find any open window matching '{window_title}'."
                    except ImportError:
                        pass # Fallback to standard active-window close if pygetwindow is missing

                # 4. Fallback Execution (Standard active window tab close)
                winsound.Beep(1000, 300)
                time.sleep(1)
                pyautogui.hotkey('ctrl', 'w')
                return "Closed the target active tab session successfully."

            return await asyncio.to_thread(_close_worker)
        except Exception as e:
            import logging
            logging.getLogger("jarvis-tools").error(f"Failed to execute tab closure layout: {e}")
            return f"Error executing tab closure: {str(e)}"

    @llm.function_tool(description="Use this tool to search YouTube. Extract ONLY the clean channel name, artist, or topic for the 'query' parameter. NEVER include words like 'latest', 'newest', or 'video' in the query string. Heuristically correct phonetic mistakes. Set search_type to 'channel_latest' if they want the newest upload from a specific creator.")
    async def search_youtube_media(self, query: str, search_type: str = "general") -> str:
        """Searches YouTube for a video matching the query.
        
        Args:
            query: The search term (e.g. 'Coldplay Yellow' or the channel name).
            search_type: Set to 'channel_latest' ONLY if the user specifically asks for the latest upload from a specific channel/creator. Otherwise, use 'general'.
        """
        if hasattr(self, '_session') and self._session:
            await self._session.say(f"Pulling up {query} on YouTube now.", allow_interruptions=True)
            
        import httpx
        api_key = os.getenv("GOOGLE_CLOUD_API_KEY") 
        if not api_key:
            return "YouTube API integration failed: GOOGLE_CLOUD_API_KEY is missing from system environment variables."
            
        url = "https://www.googleapis.com/youtube/v3/search"
        
        try:
            async with httpx.AsyncClient() as client:
                if search_type == "channel_latest":
                    # Step 1: Find the channel ID
                    channel_params = {
                        "q": query,
                        "part": "snippet",
                        "type": "channel",
                        "maxResults": 1,
                        "key": api_key
                    }
                    c_resp = await client.get(url, params=channel_params, timeout=5.0)
                    c_items = c_resp.json().get("items", [])
                    
                    if not c_items:
                        return f"I searched for the channel '{query}' but couldn't find it."
                        
                    channel_id = c_items[0]["snippet"]["channelId"]
                    
                    # Step 2: Get the latest video for that channel
                    video_params = {
                        "channelId": channel_id,
                        "part": "snippet",
                        "type": "video",
                        "maxResults": 1,
                        "order": "date",
                        "key": api_key
                    }
                    v_resp = await client.get(url, params=video_params, timeout=5.0)
                    data = v_resp.json()
                else:
                    # General relevance search
                    params = {
                        "q": query,
                        "part": "snippet",
                        "type": "video",
                        "maxResults": 1,
                        "order": "relevance",
                        "key": api_key
                    }
                    resp = await client.get(url, params=params, timeout=5.0)
                    data = resp.json()
                
            items = data.get("items", [])
            if not items:
                return f"I searched YouTube but couldn't find any media matching '{query}'."
                
            video_id = items[0]["id"]["videoId"]
            title = items[0]["snippet"]["title"]
            video_url = f"https://youtube.com/watch?v={video_id}"
            
            import asyncio
            await asyncio.to_thread(self.sys_ctrl.open_url, video_url)
            return f"Successfully located '{title}' on YouTube and initiated playback system initialization."
        except Exception as e:
            return f"Failed to interface with YouTube telemetry cluster. Error: {str(e)}"

    @llm.function_tool(description="Adds a new appointment, reminder, or event to the user's local schedule agenda.")
    async def add_agenda_event(self, event_description: str, date_time: str) -> str:
        """Local persistent scheduler system mapping."""
        agenda_path = os.path.join(self.notes_dir, "agenda.md")
        
        def _write_agenda():
            if not os.path.exists(agenda_path):
                with open(agenda_path, "w", encoding="utf-8") as f:
                    f.write("# JARVIS NUCLEUS AGENDA\n\n")
            with open(agenda_path, "a", encoding="utf-8") as f:
                f.write(f"- **[{date_time}]**: {event_description}\n")
                
        try:
            import asyncio
            await asyncio.to_thread(_write_agenda)
            return f"Successfully added to your local agenda: '{event_description}' scheduled for {date_time}."
        except Exception as e:
            return f"Failed to write to local agenda storage. Error: {str(e)}"

    @llm.function_tool(description="Retrieves all scheduled appointments and reminders from the user's local agenda file.")
    async def view_agenda_events(self) -> str:
        """Reads the entire schedule file to check what the user has planned."""
        agenda_path = os.path.join(self.notes_dir, "agenda.md")
        
        def _read_agenda():
            if not os.path.exists(agenda_path) or os.path.getsize(agenda_path) < 30:
                return "Your current agenda file is completely empty. You have no events scheduled."
            with open(agenda_path, "r", encoding="utf-8") as f:
                return f"Here is the current scheduled agenda context:\n{f.read()}"
                
        try:
            import asyncio
            content = await asyncio.to_thread(_read_agenda)
            return content
        except Exception as e:
            return f"Failed to retrieve local agenda streams. Error: {str(e)}"

    @llm.function_tool(description="Changes the system volume level. Provide an integer between 0 and 100.")
    async def set_volume(self, level: int) -> str:
        """Sets the master OS execution volume mixer channel via threaded COM isolation contexts."""
        try:
            target_level = max(0, min(100, int(level)))
            
            def _set_vol_worker(vol_level: int):
                import comtypes
                from pycaw.pycaw import AudioUtilities
                
                # Setup proper single-threaded apartment COM allocation structures
                comtypes.CoInitialize()
                try:
                    devices = AudioUtilities.GetSpeakers()
                    volume = devices.EndpointVolume
                    scalar_val = float(vol_level) / 100.0
                    volume.SetMasterVolumeLevelScalar(scalar_val, None)
                finally:
                    comtypes.CoUninitialize()

            import asyncio
            await asyncio.to_thread(_set_vol_worker, target_level)
            return f"System volume successfully set to {target_level}%."
        except Exception as e:
            return f"Failed to alter hardware audio system configuration channel. Error: {e}"

    @llm.function_tool(description="Cross-references controversial claims or viral news items against global registries.")
    async def verify_claim_truth(self, claim_query: str) -> str:
        """Dispatches analytical parameters to Google Fact Check registry hubs."""
        import httpx
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
                return f"No official fact-check records found matching the claim: '{claim_query}'."
                
            first_match = claims[0]
            text = first_match.get("text", "Unknown Claim")
            review = first_match.get("claimReview", [{}])[0]
            publisher = review.get("publisher", {}).get("name", "Independent Auditor")
            rating = review.get("textualRating", "Unverified")
            
            return f"Fact Check Audit for '{text}': Evaluated by {publisher} as '{rating}'."
        except Exception as e:
            return f"Failed to link to the Google Fact Check cluster. Error: {str(e)}"

    @llm.function_tool(description="Sends a compiled research summary or notification email directly to the user's personal inbox.")
    async def send_research_email(self, recipient_email: str, email_subject: str, email_body_content: str) -> str:
        """Sends analytical payload documents out to third party mail hosts via SendGrid transaction pipes."""
        import httpx
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        sender_identity = os.getenv("JARVIS_EMAIL_IDENTITY")
        
        if not sendgrid_key or not sender_identity:
            return "Email transmission aborted: Configuration values for SENDGRID_API_KEY or JARVIS_EMAIL_IDENTITY are missing."
            
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {sendgrid_key}",
            "Content-Type": "application/json"
        }
        
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

    @llm.function_tool(description="Launches an authorized desktop application from the local registry database. Input must be the simple short name of the application (e.g., 'vscode', 'chrome').")
    async def launch_application(self, app_name: str) -> str:
        """
        Securely matches and executes local applications via a dynamic JSON mapping configuration using native Windows shell hooks.
        """
        import os
        import json
        import asyncio
        import logging

        # Save the registry config file right inside the sandboxed documents folder
        config_path = os.path.join(self.notes_dir, "app_registry.json")
        
        # Default baseline registry mapping to spin up automatically
        default_registry = {
            "vscode": "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe",
            "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "spotify": "%APPDATA%\\Spotify\\Spotify.exe",
            "notepad": "C:\\Windows\\System32\\notepad.exe",
            "calculator": "C:\\Windows\\System32\\calc.exe"
        }

        def _handle_registry():
            logger = logging.getLogger("jarvis-profile")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read app_registry.json, reverting to defaults: {e}")
            else:
                try:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(default_registry, f, indent=4)
                except Exception as e:
                    logger.error(f"Could not initialize app_registry.json: {e}")
            return default_registry

        # Isolate all synchronous file I/O into a background thread to prevent audio jitter
        registry = await asyncio.to_thread(_handle_registry)

        # Normalize the string input to catch case variations
        target_key = app_name.lower().strip()
        
        if target_key not in registry:
            valid_options = ", ".join(registry.keys())
            return f"Execution denied: '{app_name}' is not registered. Registered apps are: {valid_options}. Instruct the user to add the executable path to app_registry.json if needed."

        # Fetch path and resolve internal Windows environment variables automatically
        target_path = os.path.expandvars(registry[target_key])

        if not os.path.exists(target_path):
            return f"Target error: Registry key verified, but path location is invalid on this filesystem: {target_path}"

        try:
            # Native Windows Shell handoff wrapped in an async thread worker to secure real-time audio integrity
            await asyncio.to_thread(os.startfile, target_path)
            return f"Successfully initialized desktop execution sequence for {target_key}."
        except Exception as e:
            return f"OS initialization fault encountered during app startup sequence. Error: {str(e)}"
