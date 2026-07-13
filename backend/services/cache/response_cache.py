import os
import logging
from difflib import SequenceMatcher
from typing import Optional
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

_CACHE_MAX_ENTRIES = 100
_SIMILARITY_THRESHOLD = 0.85


class ResponseCache:
    """
    Caches LLM responses for similar user prompts using fuzzy matching.

    Adapted from thevickypedia/Jarvis GPT response caching pattern.
    Uses YAML for persistence across restarts (human-readable, easy to audit).
    """

    def __init__(self, cache_file: str = "response_cache.yaml"):
        self.cache_file = cache_file
        self._cache: dict[str, dict] = {}
        self._load()

    def _load(self):
        if yaml is None:
            logger.warning("PyYAML not installed; response cache disabled")
            return
        try:
            if os.path.isfile(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._cache = data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"Failed to load response cache: {e}")
            self._cache = {}

    def _save(self):
        if yaml is None:
            return
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                yaml.dump(self._cache, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Failed to save response cache: {e}")

    def get(self, user_message: str) -> Optional[str]:
        """Return a cached response if a similar prompt exists above the threshold."""
        if not user_message or not self._cache:
            return None

        user_lower = user_message.lower().strip()
        for cached_q, entry in self._cache.items():
            similarity = SequenceMatcher(None, user_lower, cached_q.lower().strip()).ratio()
            if similarity >= _SIMILARITY_THRESHOLD:
                logger.info(f"Cache hit ({similarity:.2f}): {user_message!r} -> {cached_q!r}")
                return entry.get("response")
        return None

    def set(self, user_message: str, response: str):
        """Store a response in the cache."""
        if not user_message or not response:
            return

        self._cache[user_message] = {
            "response": response,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        # LRU eviction: keep only newest N entries
        if len(self._cache) > _CACHE_MAX_ENTRIES:
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1].get("cached_at", ""),
                reverse=True,
            )[:_CACHE_MAX_ENTRIES]
            self._cache = dict(sorted_items)

        self._save()


response_cache = ResponseCache()
