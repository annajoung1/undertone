#!/usr/bin/env python3
"""진짜 사람 목소리에서 톤 엔진이 작동하는지 검증. 같은 문장을 두 번 말한다."""
import sys, os, wave
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "undertone"))
import numpy as np, sounddevice as sd
import tone, config

SR, SECS = 24000, 5
LINE = "Yeah, it was nice. I liked it."

TAKES = [
    ("예의상 (시큰둥)", "관심 없는데 예의상 좋다고 하는 말투로. 낮고 평평하게, 천천히."),
    ("진심 (활기참)",   "진짜 좋았던 것처럼. 밝고 빠르게, 억양 살려서."),
]

print(f"\n같은 문장을 두 가지 말투로 말합니다:  \033[1m\"{LINE}\"\033[0m")
res = {}
for label, how in TAKES:
    input(f"\n[{label}]  {how}\n  준비되면 Enter → {SECS}초 녹음")
    print("  🔴 녹음중...")
    rec = sd.rec(int(SECS*SR), samplerate=SR, channels=1, dtype="int16"); sd.wait()
    pcm = rec.tobytes()
    p = tone.analyze(pcm, len(LINE.split()))
    res[label] = p
    with wave.open(f"example_outputs/human_{'flat' if '예의상' in label else 'warm'}.wav","wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
    col = "\033[31m" if p.engagement < config.FLAT_ENGAGEMENT else "\033[32m"
    print(f"  → engagement {col}{p.engagement}\033[0m  (피치폭 {p.pitch_range_st} st · "
          f"속도 {p.speech_rate_wps} w/s · 휴지 {int(p.pause_ratio*100)}%)")
    print(f"    {p.reading}")

a, b = [res[k].engagement for k,_ in TAKES]
print(f"\n{'='*58}")
print(f"편차 {b-a}점")
if b-a >= 25 and a < config.FLAT_ENGAGEMENT:
    print("✅ 진짜 사람 목소리에서 확실히 갈림 — 라이브 데모 가능")
elif b-a >= 15:
    print("🔶 갈리긴 하는데 약함 — 임계값 조정 필요")
else:
    print("❌ 구분 안 됨 — 시뮬레이션 응답자로 가야 함")
