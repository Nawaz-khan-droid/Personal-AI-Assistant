import logging
from typing import List, Dict, Any
from ddgs import DDGS  # pip package: ddgs (formerly duckduckgo-search)

from backend.utils.retry import retry

logger = logging.getLogger(__name__)


@retry(attempts=2, interval=1.0, exclude_exc=(ValueError,))
def fetch_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search DuckDuckGo using the duckduckgo-search library (scrapes HTML).
    Retried once on failure for transient rate-limit/network issues.
    """
    results = []
    with DDGS() as ddgs:
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

if __name__ == "__main__":
    # Quick test
    print("Testing DuckDuckGo Search...")
    res = fetch_duckduckgo("current time in Tokyo")
    for item in res:
        print(f"- {item['title']}: {item['url']}")
