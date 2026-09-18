#!/usr/bin/env python3
"""Check that the tone engine separates your own voice. Retake until you are happy."""
import sys, os, wave
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "undertone"))
import numpy as np, sounddevice as sd
import tone, config

SR = 24000
LINE = "Yeah, it was nice. I liked it."
C = dict(b="\033[1m", r="\033[0m", gy="\033[90m", rd="\033[31m", gr="\033[32m", ye="\033[33m")

TAKES = [
    ("flat", "Polite, unenthused", [
        "Like you are half looking at your phone",
        "Let the ending fall - \"nice\", not \"nice?\"",
        "Slower, lower, a little quieter",
        "Leave small gaps: \"Yeah... it was nice. I liked it.\"",
    ]),
    ("warm", "Like you meant it", [
        "The way you would tell a friend about something you loved",
        "Lean on \"nice\" and \"liked\"",
        "Faster, ending up",
    ]),
]


def record():
    input(f"  {C['b']}[Enter] to start recording{C['r']}")
    frames, stop = [], False
    st = sd.InputStream(samplerate=SR, channels=1, dtype="int16"); st.start()
    print(f"  {C['rd']}🔴 recording{C['r']} — [Enter] when done")
    import threading
    ev = threading.Event()
    threading.Thread(target=lambda: (input(), ev.set()), daemon=True).start()
    while not ev.is_set() and len(frames) * 1024 / SR < 15:
        d, _ = st.read(1024); frames.append(d)
    st.stop(); st.close()
    return np.concatenate(frames).tobytes() if frames else b""


print(f"\nSay the same line two ways:  {C['b']}\"{LINE}\"{C['r']}")
res = {}
for key, label, tips in TAKES:
    print(f"\n{'='*58}\n{C['b']}[{label}]{C['r']}")
    for t in tips:
        print(f"  {C['gy']}·{C['r']} {t}")
    while True:
        pcm = record()
        if not pcm:
            print("  nothing recorded, try again"); continue
        p = tone.analyze(pcm, len(LINE.split()))
        col = C["rd"] if p.engagement < config.FLAT_ENGAGEMENT else C["gr"]
        print(f"\n  → engagement {col}{C['b']}{p.engagement}{C['r']}   "
              f"{C['gy']}pitch range {p.pitch_range_st} st · {p.speech_rate_wps} words/s · "
              f"{int(p.pause_ratio*100)}% pause · {p.duration_s}s{C['r']}")
        print(f"    {p.reading}")
        print(f"\n  {C['gy']}playing it back — keep this take? [Enter = keep / r = retake]{C['r']}")
        sd.play(np.frombuffer(pcm, dtype="<i2"), SR); sd.wait()
        if input("  > ").strip().lower() not in ("r", "re", "retake"):
            res[key] = p
            with wave.open(f"example_outputs/human_{key}.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
            break

a, b = res["flat"].engagement, res["warm"].engagement
print(f"\n{'='*58}")
print(f"  polite {a}   vs   sincere {b}     spread {C['b']}{b-a}{C['r']}")
if b - a >= 25 and a < config.FLAT_ENGAGEMENT:
    print(f"  {C['gr']}clearly separated — your voice works for a live demo{C['r']}")
elif b - a >= 15:
    print(f"  {C['ye']}separated, but weakly — try exaggerating the flat take{C['r']}")
else:
    print(f"  {C['rd']}not separated{C['r']}")
