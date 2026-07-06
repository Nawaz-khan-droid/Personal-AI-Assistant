import logging
from typing import Dict, Any

from ..tool_registry import Tool, registry
from backend.services.duckduckgo_service import fetch_duckduckgo

logger = logging.getLogger(__name__)


class WebSearchTool(Tool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo. Returns up to 5 search results with titles, snippets, and URLs."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query."
                }
            },
            "required": ["query"]
        }

    async def execute(self, query: str) -> str:
        try:
            results = fetch_duckduckgo(query, max_results=5)
            if not results:
                return f"No search results found for '{query}'."
            lines = [f"Search results for '{query}':"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "Untitled")
                desc = r.get("description", "")
                url = r.get("url", "")
                lines.append(f"{i}. {title} - {desc} ({url})")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Web search tool error: {e}")
            return f"Error searching for '{query}': {e}"


registry.register(WebSearchTool())
