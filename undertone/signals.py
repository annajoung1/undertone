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


class Baseline:
    """화자 본인의 기준선. 사람마다 기본 억양 폭이 다르므로 절대값으로 자르면 안 된다.

    실측 근거: 같은 사람이 같은 문장을 '시큰둥하게' 읽으면 75, '진심으로' 읽으면 96이 나왔다.
    75는 절대값으로는 전혀 낮지 않다. 낮은 것은 '본인 기준으로' 21점 떨어졌다는 사실이다.
    그래서 판정은 언제나 그 사람 자신과의 비교로 한다 (speaker normalization).
    """

    def __init__(self, drop: int):
        self.drop = drop
        self.samples = []

    def observe(self, engagement):
        if engagement:
            self.samples.append(engagement)

    @property
    def value(self):
        # 앞쪽 발화들의 최고치를 그 사람의 '평소 톤'으로 삼는다.
        return max(self.samples) if self.samples else None

    @property
    def ready(self):
        return len(self.samples) >= 1


def check_mismatch(text: str, prosody, baseline: "Baseline") -> dict:
    """어휘와 운율이 어긋나는지 본다. 판정 기준은 화자 자신의 기준선이다."""
    w = classify_words(text)
    eng = getattr(prosody, "engagement", None)
    base = baseline.value if baseline else None
    out = {"words": w, "engagement": eng, "baseline": base, "mismatch": False}

    if eng is None:
        return {**out, "why": "운율 측정 없음"}
    if not base or not baseline.ready:
        return {**out, "why": f"기준선 수집 중 (engagement {eng})"}

    delta = eng - base
    flat = delta <= -baseline.drop
    positive_words = w["label"] in ("hedged_positive", "strong_positive")

    if positive_words and flat:
        return {**out, "mismatch": True, "delta": delta,
                "why": (f"긍정어({', '.join(w['hedges'] + w['strong'])[:30]})를 썼지만 "
                        f"본인 평소 톤보다 {abs(delta)}점 낮음 ({base}→{eng}) "
                        f"— 예의상 답변일 가능성")}
    if w["label"] == "negative" and not flat:
        return {**out, "delta": delta,
                "why": f"부정적 내용을 톤도 실어서 말함 ({eng}) — 진심으로 보임"}
    return {**out, "delta": delta,
            "why": f"어휘({w['label']})와 톤이 일치 ({eng}, 기준선 {base})"}
