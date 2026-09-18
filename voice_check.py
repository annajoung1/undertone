#!/usr/bin/env python3
"""진짜 사람 목소리에서 톤 엔진이 작동하는지 검증. 마음에 안 들면 다시 찍을 수 있다."""
import sys, os, wave
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "undertone"))
import numpy as np, sounddevice as sd
import tone, config

SR = 24000
LINE = "Yeah, it was nice. I liked it."
C = dict(b="\033[1m", r="\033[0m", gy="\033[90m", rd="\033[31m", gr="\033[32m", ye="\033[33m")

TAKES = [
    ("flat", "예의상 (시큰둥)", [
        "폰 보면서 건성으로 대답하듯이",
        "끝을 올리지 말 것 — \"nice↗\" 가 아니라 \"nice↘\"",
        "천천히, 목소리 낮게, 좀 작게",
        "\"Yeah... it was nice. I liked it.\" 처럼 사이를 살짝 두기",
    ]),
    ("warm", "진심 (활기참)", [
        "진짜 좋았던 걸 친구한테 말하듯이",
        "\"nice\" 랑 \"liked\" 를 세게 강조",
        "빠르게, 끝을 올려서",
    ]),
]


def record():
    input(f"  {C['b']}[Enter] 녹음 시작{C['r']}")
    frames, stop = [], False
    st = sd.InputStream(samplerate=SR, channels=1, dtype="int16"); st.start()
    print(f"  {C['rd']}🔴 녹음중{C['r']} — 말 끝나면 [Enter]")
    import threading
    ev = threading.Event()
    threading.Thread(target=lambda: (input(), ev.set()), daemon=True).start()
    while not ev.is_set() and len(frames) * 1024 / SR < 15:
        d, _ = st.read(1024); frames.append(d)
    st.stop(); st.close()
    return np.concatenate(frames).tobytes() if frames else b""


print(f"\n같은 문장을 두 가지 말투로:  {C['b']}\"{LINE}\"{C['r']}")
res = {}
for key, label, tips in TAKES:
    print(f"\n{'='*58}\n{C['b']}[{label}]{C['r']}")
    for t in tips:
        print(f"  {C['gy']}·{C['r']} {t}")
    while True:
        pcm = record()
        if not pcm:
            print("  녹음 실패, 다시"); continue
        p = tone.analyze(pcm, len(LINE.split()))
        col = C["rd"] if p.engagement < config.FLAT_ENGAGEMENT else C["gr"]
        print(f"\n  → engagement {col}{C['b']}{p.engagement}{C['r']}   "
              f"{C['gy']}피치폭 {p.pitch_range_st} st · 속도 {p.speech_rate_wps} w/s · "
              f"휴지 {int(p.pause_ratio*100)}% · {p.duration_s}초{C['r']}")
        print(f"    {p.reading}")
        print(f"\n  {C['gy']}들어보기: 이 테이크 쓸까? [Enter=쓴다 / r=다시]{C['r']}")
        sd.play(np.frombuffer(pcm, dtype="<i2"), SR); sd.wait()
        if input("  > ").strip().lower() not in ("r", "re", "다시"):
            res[key] = p
            with wave.open(f"example_outputs/human_{key}.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
            break

a, b = res["flat"].engagement, res["warm"].engagement
print(f"\n{'='*58}")
print(f"  시큰둥 {a}   vs   진심 {b}     편차 {C['b']}{b-a}점{C['r']}")
if b - a >= 25 and a < config.FLAT_ENGAGEMENT:
    print(f"  {C['gr']}✅ 확실히 갈림 — 라이브 데모로 간다{C['r']}")
elif b - a >= 15:
    print(f"  {C['ye']}🔶 갈리지만 약함 — 임계값 조정하면 됨{C['r']}")
else:
    print(f"  {C['rd']}❌ 구분 안 됨{C['r']}")
