"""Measures prosody directly from response audio.

This module is the core of the product. A speech-to-text pipeline cannot produce these
numbers, because by the time text arrives the delivery is gone. That is the reason for
using a speech-to-speech model.

Honesty rule: what is measured here is prosody, not emotion. Speaking rate, pause ratio,
pitch range, energy variation. Emotion would be an interpretation of those numbers, and
this module does not make it. signals.py compares them against the speaker's own baseline;
nothing here claims to know how anyone feels.
"""
from dataclasses import dataclass, asdict
import numpy as np

SR = 24000
FRAME = int(0.025 * SR)   # 25ms
HOP = int(0.010 * SR)     # 10ms
F0_MIN, F0_MAX = 70, 350


@dataclass
class Prosody:
    duration_s: float
    speech_rate_wps: float     # words per second over total duration
    pause_ratio: float         # fraction of frames below the silence threshold
    pitch_median_hz: float
    pitch_range_st: float      # 10th-90th percentile F0 spread, in semitones
    energy_cv: float           # coefficient of variation of frame energy
    engagement: int            # 0-100 weighted composite (see below)
    reading: str               # filled in by signals.py, not here

    def as_dict(self):
        return asdict(self)


def _frames(x):
    n = 1 + max(0, (len(x) - FRAME) // HOP)
    return np.lib.stride_tricks.as_strided(
        x, shape=(n, FRAME), strides=(x.strides[0] * HOP, x.strides[0])
    ) if n > 0 else np.empty((0, FRAME))


def _f0(frame, sr=SR):
    """Autocorrelation-based F0 estimate for one frame."""
    f = frame - frame.mean()
    if np.abs(f).max() < 1e-6:
        return 0.0
    corr = np.correlate(f, f, mode="full")[len(f) - 1:]
    lo, hi = sr // F0_MAX, min(sr // F0_MIN, len(corr) - 1)
    if hi <= lo:
        return 0.0
    seg = corr[lo:hi]
    peak = int(np.argmax(seg)) + lo
    if corr[0] <= 0 or corr[peak] / corr[0] < 0.3:   # discard weak periodicity
        return 0.0
    return sr / peak


def analyze(pcm: bytes, word_count: int) -> Prosody:
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float64) / 32768.0
    dur = len(x) / SR
    if dur < 0.3:
        return Prosody(dur, 0, 0, 0, 0, 0, 0, "too short to measure")

    fr = _frames(x)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)

    # Adaptive silence threshold: 15% of the 90th-percentile frame energy
    thr = max(np.percentile(rms, 90) * 0.15, 1e-4)
    voiced = rms > thr
    pause_ratio = float(1.0 - voiced.mean())
    voiced_s = float(voiced.sum() * HOP / SR) or 1e-6

    rate = word_count / voiced_s   # articulation rate, kept for reference

    f0s = np.array([_f0(fr[i]) for i in np.where(voiced)[0]])
    f0s = f0s[f0s > 0]
    if len(f0s) >= 5:
        p_med = float(np.median(f0s))
        lo, hi = np.percentile(f0s, [10, 90])
        p_range = float(12 * np.log2(hi / lo)) if lo > 0 else 0.0
    else:
        p_med, p_range = 0.0, 0.0

    e_cv = float(rms[voiced].std() / (rms[voiced].mean() + 1e-12)) if voiced.any() else 0.0

    # --- Composite ---------------------------------------------------------
    # engagement is a weighted sum of three prosodic axes. On its own it asserts nothing
    # about emotion.
    #
    # Weighting rationale: F0 variability is the most stable prosodic correlate of arousal
    # and engagement in the speech literature, and it separated synthesized speech most
    # reliably in our own measurements (15.1 st when the model was told to sound excited
    # vs 7.5 st when told to sound bored).
    #
    # It does NOT always move for humans. On the pair in example_outputs/, the flat take
    # scores HIGHER on pitch range (17.1 st vs 12.7 st) and separates on rate instead.
    # This is exactly why the composite is read against a per-speaker baseline on every
    # axis (see signals.Baseline) rather than thresholded on pitch alone.
    #
    # Speaking rate is computed over total duration, not voiced duration. Measured over
    # voiced frames only, a hesitant utterance paradoxically scores as fast.
    speaking_rate = word_count / dur

    s_pitch = np.clip((p_range - 4.0) / 8.0, 0, 1)        # 4-12 semitones
    s_rate = np.clip((speaking_rate - 1.2) / 1.6, 0, 1)   # 1.2~2.8 wps
    s_pause = np.clip((0.45 - pause_ratio) / 0.25, 0, 1)
    engagement = int(round(100 * (0.55 * s_pitch + 0.25 * s_rate + 0.20 * s_pause)))

    # No absolute verdict here. signals.py interprets this against the speaker's baseline.
    reading = ""

    return Prosody(round(dur, 2), round(speaking_rate, 2), round(pause_ratio, 3),
                   round(p_med, 1), round(p_range, 2), round(e_cv, 3),
                   engagement, reading)
