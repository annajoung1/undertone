"""말(내용)과 톤(운율)의 불일치를 판정한다.

원칙: 감정을 추측하지 않는다. 두 개의 독립된 관찰을 나란히 놓고 어긋나는지만 본다.
  - 관찰 A: 어휘.   긍정어를 썼나? 완충어(hedge)를 썼나?
  - 관찰 B: 운율.   실제로 톤이 올라갔나? (tone.py 가 오디오에서 측정)

둘이 어긋나면 그게 신호다. 어느 쪽이 '진실'인지는 주장하지 않는다.
대신 인터뷰어가 더 파고들어서 확인하게 만든다. 확인된 답이 진실이다.
"""
import re

# 예의상 긍정 — 미국 영어에서 '나쁘지 않다'의 완곡어법
HEDGES = [
    "nice", "fine", "okay", "ok", "pretty good", "not bad", "interesting",
    "decent", "alright", "i guess", "kind of", "kinda", "sort of", "i mean",
    "it was good", "pretty nice", "yeah no",
]
STRONG_POS = [
    "love", "loved", "amazing", "obsessed", "incredible", "fantastic",
    "definitely", "absolutely", "repurchase", "bought another", "can't wait",
]
NEGATIVE = [
    "didn't", "did not", "wouldn't", "would not", "too expensive", "dried out",
    "disappointed", "not worth", "meh", "problem", "issue", "annoying",
    "fell off", "loose", "irritat", "honestly",
]


def _hits(text, table):
    t = text.lower()
    return [w for w in table if w in t]


def classify_words(text: str) -> dict:
    """어휘만 보고 분류한다. 오디오는 보지 않는다."""
    h, s, n = _hits(text, HEDGES), _hits(text, STRONG_POS), _hits(text, NEGATIVE)
    if n and not s:
        label = "negative"
    elif s:
        label = "strong_positive"
    elif h:
        label = "hedged_positive"
    else:
        label = "neutral"
    return {"label": label, "hedges": h, "strong": s, "negative": n}


def check_mismatch(text: str, prosody, flat_threshold: int) -> dict:
    """어휘와 운율이 어긋나는지 본다."""
    w = classify_words(text)
    eng = getattr(prosody, "engagement", None)
    if eng is None:
        return {"mismatch": False, "words": w, "engagement": None, "why": "운율 측정 없음"}

    flat = eng < flat_threshold
    positive_words = w["label"] in ("hedged_positive", "strong_positive")

    if positive_words and flat:
        return {
            "mismatch": True, "words": w, "engagement": eng,
            "why": (f"긍정어({', '.join(w['hedges'] + w['strong'])[:40]})를 썼지만 "
                    f"톤이 평평함 (engagement {eng}) — 예의상 답변일 가능성"),
        }
    if w["label"] == "negative" and not flat:
        return {
            "mismatch": False, "words": w, "engagement": eng,
            "why": f"부정적 내용을 톤도 실어서 말함 (engagement {eng}) — 진심으로 보임",
        }
    return {
        "mismatch": False, "words": w, "engagement": eng,
        "why": f"어휘({w['label']})와 톤(engagement {eng})이 일치",
    }
