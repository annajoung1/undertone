"""Competitor price lookup, called as a tool mid-conversation.

With a Tavily key it searches live. Without one it falls back to a curated table of real
US retail prices - not invented numbers. The report always states which source was used.
"""
import json, os, urllib.request

from config import PRODUCT

_ANCHORS = PRODUCT["category_anchors_usd"]

TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "").strip()


def lookup_competitor(query: str) -> dict:
    """Find the current US retail price of a competing product."""
    if TAVILY_KEY:
        try:
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=json.dumps({
                    "api_key": TAVILY_KEY,
                    "query": f"{query} price US Amazon Sephora 2026",
                    "max_results": 3,
                    "search_depth": "basic",
                }).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            hits = [{"title": x.get("title"), "snippet": x.get("content", "")[:200],
                     "url": x.get("url")} for x in data.get("results", [])[:3]]
            if hits:
                return {"source": "tavily_live_search", "query": query, "results": hits}
        except Exception as e:
            pass  # fall through to the curated table

    # Fallback: curated real US retail prices
    q = query.lower()
    hits = [{"product": k, "us_price_usd": v}
            for k, v in _ANCHORS.items()
            if any(w in k.lower() for w in q.split() if len(w) > 3)]
    if not hits:
        hits = [{"product": k, "us_price_usd": v} for k, v in list(_ANCHORS.items())[:4]]
    return {"source": "curated_us_market_prices_2026", "query": query, "results": hits}


TOOL_SPEC = {
    "type": "function",
    "name": "lookup_competitor",
    "description": (
        "Look up the real current US retail price of a competing skincare product. "
        "Call this whenever you want to compare the pitched product against something "
        "you'd actually buy, or when you're unsure what a competitor costs today."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Product or category to price check, e.g. 'COSRX snail mucin serum'",
            }
        },
        "required": ["query"],
    },
}
