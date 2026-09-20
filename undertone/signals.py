"""Detects disagreement between what someone said and how they said it.

The rule here is to never guess at emotion. Two independent observations are placed side
by side, and only their disagreement is reported:
  - Observation A: the words.    Positive? Hedged?
  - Observation B: the delivery. Measured from the audio by tone.py.

When the two disagree, that is the signal. This module does not decide which one is true.
It makes the interviewer ask a harder follow-up instead. The answer to that follow-up is
the truth.
"""
import re

# Polite positives - how American English says "not bad" without saying it
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
    """Classifies the words only. Never looks at the audio."""
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
    """A speaker's own baseline.

    Different people go flat along different axes. All of these were measured, not assumed:
      - Higgs TTS separated on pitch range      (15.1 st -> 7.5 st)
      - A real human separated on speaking rate (2.07 w/s -> 1.21 w/s, while their
        pitch range actually went UP)
      - The same pattern again, 2026-09-19, on the pair committed in example_outputs/:
        2.25 w/s -> 1.41 w/s while pitch range rose 12.7 st -> 17.1 st. Reproducible
        from the checked-in .wav files, so this one you can verify yourself.
    Watching a single axis therefore misses people, and would have called the flat take
    the livelier one in two of the three cases above. Any axis that falls well below this
    speaker's own peak counts as a drop.

    This is also why no absolute threshold is used anywhere. A score of 60 is not low. It
    is a signal only because it sits 16 points under what this particular person normally
    sounds like.
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
        """How far each axis has fallen, in percent, from this speaker's own peak."""
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
    """Compares words against delivery. The reference is always the speaker themselves."""
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

    # A fall of 25% or more on any axis counts as flatter than this person's norm
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
