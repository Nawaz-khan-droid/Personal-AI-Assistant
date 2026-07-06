import os
import json
import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Dict, Any, Optional, Union

import httpx
from groq import Groq
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log

from backend import config
from backend.utils.exceptions import LLMError, RateLimitError, AIServiceError

logger = logging.getLogger(__name__)

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class TokenBucketRateLimiter:
    def __init__(self, requests_per_minute: int):
        self.capacity = requests_per_minute
        self.tokens = float(requests_per_minute)
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            refill = (now - self.last_refill) * (self.capacity / 60.0)
            self.tokens = min(self.capacity, self.tokens + refill)
            self.last_refill = now
            if self.tokens < 1:
                wait = (1 - self.tokens) * (60.0 / self.capacity)
                logger.warning(f"Rate limit hit, waiting {wait:.2f}s")
                await asyncio.sleep(wait)
                return await self.acquire()
            self.tokens -= 1
            return True


class LLMService:
    """
    Dual-LLM Router with proactive (TokenBucket) + reactive (Tenacity) rate limiting.
    Primary: Groq (llama-3.3-70b-versatile) — 300+ tok/s via LPU
    Fallback: Gemini 2.0 Flash — free tier, robust API
    Tool calling: uses ToolRegistry from backend.services.tools
    """

    def __init__(self):
        self.groq_api_key = os.environ.get("GROQ_API_KEY", config.GROQ_API_KEY)
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", config.GEMINI_API_KEY)

        self.groq_client: Optional[Groq] = None
        self.gemini_client: Optional[genai.Client] = None
        self.model_health_snapshot: Dict[str, Any] = {}
        self._tool_schema: Optional[List[Dict]] = None

        try:
            limit_str = config.LLM_RATE_LIMIT.split('/')[0]
            self.rate_limiter = TokenBucketRateLimiter(int(limit_str))
        except Exception:
            self.rate_limiter = TokenBucketRateLimiter(15)

        if not self.groq_api_key and not self.gemini_api_key:
            logger.error("No LLM API keys found. LLM services will fail.")

    @property
    def tools_schema(self) -> List[Dict]:
        if self._tool_schema is None:
            try:
                from backend.services.tools import registry
                self._tool_schema = registry.list_tools()
                logger.info(f"Loaded {len(self._tool_schema)} tool schemas")
            except Exception as e:
                logger.warning(f"Could not load tool schemas: {e}")
                self._tool_schema = []
        return self._tool_schema

    def _get_groq(self) -> Groq:
        if not self.groq_client:
            if not self.groq_api_key:
                raise LLMError("Groq API key is missing")
            self.groq_client = Groq(api_key=self.groq_api_key)
        return self.groq_client

    def _get_gemini(self) -> genai.Client:
        if not self.gemini_client:
            if not self.gemini_api_key:
                raise LLMError("Gemini API key is missing")
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        return self.gemini_client

    async def chat_complete(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        provider: Optional[str] = None
    ) -> Union[str, AsyncGenerator[str, None]]:
        await self.rate_limiter.acquire()
        merged_tools = tools if tools is not None else self.tools_schema

        try:
            return await self._call_groq(messages, system_prompt, temperature, max_tokens, stream, merged_tools)
        except Exception as e:
            logger.warning(f"Groq primary failed after retries: {e}. Trying Gemini fallback...")
            try:
                return await self._call_gemini(messages, system_prompt, temperature, max_tokens, stream)
            except Exception as gemini_err:
                raise LLMError(f"Both LLMs failed. Groq: {e} | Gemini: {gemini_err}")

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Only retry on rate limits (429) and transient network errors."""
        if hasattr(exc, 'status_code') and exc.status_code == 429:
            return True
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, ConnectionError, TimeoutError)):
            return True
        return False

    def _groq_create(self, client, **kwargs):
        """Synchronous Groq call wrapped with Tenacity retry."""
        return client.chat.completions.create(**kwargs)

    async def _call_groq(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        tools: Optional[List[Dict]] = None
    ) -> Union[str, AsyncGenerator[str, None]]:
        client = self._get_groq()

        final_messages = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.extend(messages)

        kwargs = {
            "model": GROQ_MODEL,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        retryable_create = retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception(self._is_retryable),
            reraise=True,
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )(self._groq_create)

        response = await asyncio.to_thread(retryable_create, client, **kwargs)

        if stream:
            return self._stream_groq(response)

        msg = response.choices[0].message
        if msg.tool_calls:
            return await self._execute_tool_calls(client, msg, final_messages, temperature, max_tokens, tools)

        return msg.content

    async def _execute_tool_calls(self, client, msg, messages, temperature, max_tokens, tools):
        from backend.services.tools import executor
        messages.append(msg)
        for tc in msg.tool_calls:
            args = {}
            if tc.function.arguments:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
            logger.info(f"Executing tool: {tc.function.name} with args: {args}")
            result = await executor.execute_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.function.name,
                "content": result,
            })
        retryable_create = retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception(self._is_retryable),
            reraise=True,
        )(self._groq_create)
        final_response = await asyncio.to_thread(
            retryable_create, client,
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return final_response.choices[0].message.content

    async def _call_gemini(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        client = self._get_gemini()
        gemini_messages = []
        for m in messages:
            if "content" in m and m["content"]:
                role = "model" if m["role"] == "assistant" else "user"
                gemini_messages.append({"role": role, "parts": [{"text": m["content"]}]})

        from google.genai import types as gemini_types
        gen_config = gemini_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_prompt,
        )
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=gemini_messages or [gemini_types.Content(role="user", parts=[gemini_types.Part.from_text(text="Hello")])],
                config=gen_config,
            )
        )
        return response.text

    async def _stream_groq(self, response) -> AsyncGenerator[str, None]:
        for chunk in response:
            try:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            except (AttributeError, IndexError):
                continue

    async def probe_gemini_models(self) -> Dict[str, Any]:
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "provider": "groq+gemini",
            "groq_model": GROQ_MODEL,
            "gemini_model": GEMINI_MODEL,
            "groq_configured": bool(self.groq_api_key),
            "gemini_configured": bool(self.gemini_api_key),
            "tools_loaded": len(self.tools_schema),
            "status": "unknown",
        }
        try:
            client = self._get_groq()
            retryable_ping = retry(
                stop=stop_after_attempt(2),
                wait=wait_exponential(multiplier=1, min=1, max=5),
                retry=retry_if_exception(self._is_retryable),
                reraise=True,
            )(self._groq_create)
            response = await asyncio.to_thread(
                lambda: retryable_ping(client, model=GROQ_MODEL, messages=[{"role": "user", "content": "ping"}], max_tokens=5)
            )
            snapshot["status"] = "Operational"
            snapshot["groq_ok"] = bool(response.choices)
        except Exception as e:
            snapshot["status"] = "Groq failed"
            snapshot["error"] = str(e)
            try:
                gclient = self._get_gemini()
                gresponse = await asyncio.to_thread(
                    lambda: gclient.models.generate_content(
                        model=GEMINI_MODEL,
                        contents="ping",
                    )
                )
                snapshot["status"] = "Gemini fallback operational"
                snapshot["gemini_ok"] = bool(gresponse.text)
            except Exception as ge:
                snapshot["gemini_error"] = str(ge)

        self.model_health_snapshot = snapshot
        return snapshot

    def get_model_health_snapshot(self) -> Dict[str, Any]:
        return self.model_health_snapshot

    async def check_health(self) -> bool:
        try:
            snap = await self.probe_gemini_models()
            return snap.get("status") in ("Operational", "Gemini fallback operational")
        except Exception:
            return False


llm_service = LLMService()
