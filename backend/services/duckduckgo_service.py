import logging
from typing import List, Dict, Any
from duckduckgo_search import DDGS  # pip package: ddgs

logger = logging.getLogger(__name__)

def fetch_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search DuckDuckGo using the duckduckgo-search library (scrapes HTML).
    This provides actual search results, unlike the Instant Answer API.
    """
    results = []
    try:
        with DDGS() as ddgs:
            # excessive usage might trigger rate limits, so we catch exceptions
            ddg_gen = ddgs.text(query, max_results=max_results)
            if ddg_gen:
                for r in ddg_gen:
                    results.append({
                        "title": r.get("title"),
                        "description": r.get("body"),
                        "url": r.get("href"),
                        "source": "duckduckgo"
                    })
        return results
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []

if __name__ == "__main__":
    # Quick test
    print("Testing DuckDuckGo Search...")
    res = fetch_duckduckgo("current time in Tokyo")
    for item in res:
        print(f"- {item['title']}: {item['url']}")
