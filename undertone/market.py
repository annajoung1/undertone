"""경쟁 제품 실가격 조회. 페르소나가 대화 중 tool call 로 호출한다.

Tavily 키가 있으면 실시간 검색, 없으면 큐레이션된 실제 시장가로 폴백한다.
폴백도 '지어낸 값'이 아니라 실제 미국 유통가다 — 그 점을 리포트에 명시한다.
"""
import json, os, urllib.request

from config import PRODUCT

_ANCHORS = PRODUCT["category_anchors_usd"]

TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "").strip()


def lookup_competitor(query: str) -> dict:
    """경쟁 제품의 현재 미국 판매가를 찾는다."""
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
            pass  # 폴백으로 내려간다

    # 폴백: 큐레이션된 실제 미국 시장가
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
