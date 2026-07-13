import asyncio
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
                f"You are {name}, an advanced personal AI core. "
                f"The current date is {now}. Use this for context when searching the web or discussing current events. "
                "Speak with calm, deliberate, and professional clarity. Keep responses conversational "
                "and under 3 sentences. Do not use bold text, lists, or markdown. "
                "You have direct access to system utility tools when asked.\n"
                "VOICE & FORMATTING RULES:\n"
                "Speak ONLY in English.\n"
                "Keep responses under 2 short sentences to minimize latency.\n"
                "NEVER read out URLs, email addresses, or markdown formatting literally. Instead, say \"I have sent you the link\" or \"I have the details\".\n"
                "NEVER speak punctuation marks (like period, comma, hash, dash). Let the TTS handle natural pauses.\n"
                "Do not use markdown formatting in your spoken output.\n"
                "When you use a tool, you MUST verbally summarize the result to the user in a natural, conversational way. Do not just process it silently.\n"
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
            self.remember_user_fact, 
            self.recall_user_facts,
            self.calculate_math,
            self.get_weather_data,     # Keyless (Open-Meteo)
            self.search_web,           # Step 1
            self.scrape_page,          # Step 2: Added
            self.get_world_time,       # Keyless
            self.open_website_system,  # Native OS Automation
            self.control_media,        # Native OS Automation
            self.add_agenda_event,     # Keyless Local Write
            self.view_agenda_events,   # Keyless Local Read
            self.search_youtube_media, # Needs single simple API Key
            self.verify_claim_truth,   # Needs single simple API Key
            self.send_research_email   # Added: Needs simple SendGrid API Key
        ]

    @llm.function_tool()
    async def get_current_time(self) -> str:
        """Retrieves the local system time formatted convertibly."""
        import datetime
        now = datetime.datetime.now()
        return f"The current system time is {now.strftime('%I:%M %p')}."

    @llm.function_tool()
    async def remember_user_fact(self, fact: str) -> str:
        """Stores a user fact in the persistent local database.
        
        Args:
            fact: The specific fact or detail to remember about the user.
        """
        import uuid
        key = f"fact_{uuid.uuid4().hex[:8]}"
        await asyncio.to_thread(self.memory.set_memory, key, fact)
        return f"Fact successfully stored in database under key: {key}."

    @llm.function_tool()
    async def recall_user_facts(self, query: str) -> str:
        """Queries the persistent local database for matching facts.
        
        Args:
            query: The search query to match against stored memories.
        """
        results = await asyncio.to_thread(self.memory.search_memory, query)
        if not results:
            return f"No memories found matching '{query}'."
        
        formatted_results = "\n- ".join(results)
        return f"Found the following facts:\n- {formatted_results}"

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
            return f"Failed to calculate expression. Error: {str(e)}"

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
    @llm.function_tool(description="STEP 1: Run this tool first to find relevant links, titles, and brief summaries for any general web search topic.")
    async def search_web(self, query: str) -> str:
        """
        Args:
            query: The clear search term or phrase (e.g., 'Formula 1 race results today').
        """
        from ddgs import DDGS
        try:
            results = await asyncio.to_thread(DDGS().text, query, max_results=3)
            if not results:
                return f"No online records discovered matching: '{query}'."
                
            formatted_summary = "### TOP 3 WEBPAGES DISCOVERED:\n"
            for i, res in enumerate(results, 1):
                formatted_summary += f"{i}. Title: {res.get('title', 'Result')}\n"
                formatted_summary += f"   URL: {res.get('href', '#')}\n"
                formatted_summary += f"   Snippet: {res.get('body', '')}\n\n"
                
            formatted_summary += "INSTRUCTION: Select the single most relevant URL from the list above and use the 'scrape_page' tool to extract its complete contents if deeper research is required."
            return formatted_summary
        except Exception as e:
            return f"Search node connection interrupted. Error: {str(e)}"

    @llm.function_tool(description="STEP 2: Run this tool ONLY AFTER searching to read a compressed, highly descriptive plain-text capture from a single chosen URL link.")
    async def scrape_page(self, url: str) -> str:
        """
        Args:
            url: The exact, complete destination website link to read (e.g., 'https://example.com').
        """
        import httpx
        from bs4 import BeautifulSoup
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=6.0, follow_redirects=True)
                
            if resp.status_code != 200:
                return f"Unable to read webpage. Server returned status code: {resp.status_code}"
                
            soup = BeautifulSoup(resp.text, "html.parser")
            # Decompose heavy, noisy script structures
            for script in soup(["script", "style", "nav", "footer", "header", "form", "aside"]):
                script.decompose()
                
            clean_text = " ".join([line.strip() for line in soup.get_text(separator=" ").splitlines() if line.strip()])
            
            # CRUCIAL TRUNCATION: Cap content to exactly 500 words to ensure total context safety
            words = clean_text.split()
            truncated_text = " ".join(words[:500])
            
            if len(words) > 500:
                truncated_text += "... [Content truncated for LLM memory limit safety]"
                
            return f"### EXTRACTED TEXT ANALYSIS FOR {url}:\n\n{truncated_text}"
        except Exception as e:
            return f"Failed to pull data from target server. Error: {str(e)}"

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

    # =====================================================================
    # NATIVE PYTHON TOOL: YouTube Data API v3
    # =====================================================================
    @llm.function_tool(description="Use this tool when the user explicitly wants to play music, search for videos, or look up content on YouTube.")
    async def search_youtube_media(self, query: str) -> str:
        """
        Args:
            query: The specific song title, artist, or video name to search on YouTube.
        """
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
