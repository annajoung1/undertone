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
    """화자 본인의 기준선.

    사람마다 '시큰둥함'이 다른 축에 나타난다. 실측에서 확인한 것:
      - Higgs TTS 는 피치 변동폭으로 갈렸다 (15.1 st -> 7.5 st)
      - 실제 사람은 발화 속도로 갈렸다 (2.07 w/s -> 1.21 w/s, 피치는 오히려 올라감)
    그래서 한 축만 보면 놓친다. 어느 축이든 본인 기준선에서 크게 벗어나면 잡는다.
    """

    def __init__(self, drop: int):
        self.drop = drop
        self.samples = []       # [(engagement, rate, pitch)]

    def observe(self, prosody):
        if prosody and getattr(prosody, "engagement", None):
            self.samples.append((prosody.engagement, prosody.speech_rate_wps,
                                 prosody.pitch_range_st))

    @property
    def ready(self):
        return len(self.samples) >= 1

    def _peak(self, i):
        return max(s[i] for s in self.samples) if self.samples else None

    @property
    def value(self):
        return self._peak(0)

    def deviations(self, prosody):
        """각 축이 본인 최고치 대비 몇 % 떨어졌는지."""
        if not self.samples or not prosody:
            return {}
        out = {}
        for i, (key, cur) in enumerate([("engagement", prosody.engagement),
                                        ("speech_rate", prosody.speech_rate_wps),
                                        ("pitch_range", prosody.pitch_range_st)]):
            base = self._peak(i)
            if base and base > 0:
                out[key] = {"base": round(base, 2), "now": round(cur, 2),
                            "pct": round((cur - base) / base * 100)}
        return out


_LABEL = {"engagement": "overall engagement", "speech_rate": "speaking rate",
          "pitch_range": "pitch range"}


def check_mismatch(text: str, prosody, baseline: "Baseline") -> dict:
    """어휘와 운율이 어긋나는지 본다. 판정 기준은 언제나 화자 자신이다."""
    w = classify_words(text)
    eng = getattr(prosody, "engagement", None)
    base = baseline.value if baseline else None
    dev = baseline.deviations(prosody) if baseline else {}
    out = {"words": w, "engagement": eng, "baseline": base,
           "deviations": dev, "mismatch": False}

    if eng is None:
        return {**out, "why": "no prosody measured", "reading": ""}
    if not base or not baseline.ready or not dev:
        return {**out, "why": "establishing this speaker's baseline",
                "reading": "baseline"}

    # 어느 축이든 25% 이상 떨어지면 '평소보다 죽은 발화'로 본다
    dropped = {k: v for k, v in dev.items() if v["pct"] <= -25}
    delta = dev.get("engagement", {}).get("now", eng) - base
    out["delta"] = round(delta)
    positive = w["label"] in ("hedged_positive", "strong_positive")

    if positive and dropped:
        worst = min(dropped.items(), key=lambda kv: kv[1]["pct"])
        k, v = worst
        return {**out, "mismatch": True,
                "reading": "flatter than this person normally speaks",
                "why": (f"said something positive (\"{(w['hedges'] + w['strong'] or [''])[0]}\") "
                        f"but their {_LABEL[k]} dropped {abs(v['pct'])}% below their own "
                        f"baseline ({v['base']} → {v['now']}) — likely being polite")}

    if w["label"] == "negative" and not dropped:
        return {**out, "reading": "delivered with full energy",
                "why": "said something critical and put energy behind it — reads as genuine"}

    if dropped:
        return {**out, "reading": "lower energy than their baseline",
                "why": f"lower energy than usual, and the words were not positive either"}

    return {**out, "reading": "consistent with their baseline",
            "why": "words and delivery agree"}
