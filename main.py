#!/usr/bin/env python3
"""Undertone — 한국 브랜드를 대신해 미국 소비자를 인터뷰하고, 말이 아니라 톤을 읽는다."""
import asyncio, json, os, sys, time, wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "undertone"))

import config, interview, report

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "example_outputs")
PLAY = "--play" in sys.argv
LIVE = "--live" in sys.argv   # 진짜 사람이 응답자

C = dict(dim="\033[2m", b="\033[1m", r="\033[0m", cy="\033[36m", ye="\033[33m",
         gr="\033[32m", rd="\033[31m", mg="\033[35m", gy="\033[90m")


def bar(v, w=24):
    f = int(round(v / 100 * w))
    col = C["gr"] if v >= 67 else (C["ye"] if v >= config.FLAT_ENGAGEMENT else C["rd"])
    return f"{col}{'█' * f}{C['gy']}{'░' * (w - f)}{C['r']}"


def play(pcm):
    if not PLAY or not pcm:
        return
    import numpy as np, sounddevice as sd
    sd.play(np.frombuffer(pcm, dtype="<i2"), 24000); sd.wait()


def on_event(kind, **kw):
    if kind == "start":
        print(f"\n{C['b']}━━━ UNDERTONE ━━━{C['r']}")
        print(f"{C['dim']}대표 브리핑 (한국어){C['r']}\n  {kw['founder_brief']}\n")
        p = config.PRODUCT
        print(f"{C['dim']}대상  {p['item']} · ${p['price_being_tested_usd']} · "
              f"{p['seeded_for']} 시딩{C['r']}")
        who = "🎤 실제 인터뷰 참여자 (마이크)" if LIVE else f"{config.RESPONDENT['name']} · {config.RESPONDENT['label']} (시뮬레이션)"
        print(f"{C['dim']}응답자 {who}{C['r']}")
        print(f"{C['dim']}{'─'*66}{C['r']}")

    elif kind == "question":
        tag = f"{C['mg']}▸ PROBE{C['r']}" if kw.get("probe") else f"{C['cy']}▸ 인터뷰어{C['r']}"
        print(f"\n{tag}  {C['gy']}({kw['turn'].first_audio_ms}ms){C['r']}")
        print(f"  {kw['text']}")
        play(kw["turn"].pcm)

    elif kind == "answer":
        print(f"\n{C['ye']}◂ {config.RESPONDENT['name']}{C['r']}")
        print(f"  {kw['text']}")
        play(kw["turn"].pcm)
        pr, sg = kw["prosody"], kw["signal"]
        if pr:
            print(f"\n  {C['dim']}톤 측정{C['r']}  {bar(pr.engagement)} {pr.engagement:>3}"
                  f"   {C['gy']}속도 {pr.speech_rate_wps} w/s · "
                  f"피치폭 {pr.pitch_range_st} st · 휴지 {int(pr.pause_ratio*100)}%{C['r']}")
            print(f"  {C['dim']}판정{C['r']}     {pr.reading}")
        if sg and sg["mismatch"]:
            print(f"  {C['rd']}{C['b']}⚠  말-톤 불일치{C['r']}  {sg['why']}")
        if kw["turn"].tool_calls:
            for t in kw["turn"].tool_calls:
                res = t["result"]
                print(f"  {C['gr']}🔍 조회{C['r']}   \"{t['args'].get('query','')}\" "
                      f"→ {C['gy']}{res['source']}{C['r']}")
                for h in res["results"][:3]:
                    print(f"           {C['gy']}{h.get('product', h.get('title',''))}: "
                          f"${h.get('us_price_usd','?')}{C['r']}")

    elif kind == "probe_triggered":
        print(f"\n  {C['mg']}{C['b']}↳ 톤이 추가 질문을 발동시킴{C['r']}")

    elif kind == "satisfaction_decided":
        print(f"\n  {C['dim']}만족도 판정 → {'긍정' if kw['satisfied'] else '부정'} "
              f"(다음 질문 분기){C['r']}")

    elif kind == "done":
        print(f"\n{C['dim']}{'─'*66}{C['r']}")
        print(f"{C['dim']}턴 {kw['turns']}개 · 도구호출 {kw['tools']}회{C['r']}")


async def main():
    t0 = time.time()
    rec = await interview.run(on_event, live=LIVE)
    os.makedirs(OUT, exist_ok=True)

    # 전체 인터뷰 오디오 하나로 저장 (심사위원이 들을 수 있게)
    allpcm = b"".join(t["pcm"] for t in rec.turns)
    with wave.open(f"{OUT}/interview.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(allpcm)

    data = [{k: v for k, v in t.items() if k != "pcm"} for t in rec.turns]
    with open(f"{OUT}/interview.json", "w") as f:
        json.dump({"product": config.PRODUCT, "brief_ko": config.FOUNDER_BRIEF_KO,
                   "respondent": config.RESPONDENT["label"], "turns": data},
                  f, ensure_ascii=False, indent=2)

    print(f"\n{C['dim']}리포트 생성중...{C['r']}")
    parts = await report.build(rec, f"{OUT}/report.html")
    print(f"\n{C['b']}결론{C['r']}  {parts[0]}")
    for l in parts[1].splitlines():
        if l.strip().startswith("-"):
            print(f"  {C['rd']}·{C['r']} {l.lstrip('- ').strip()}")

    print(f"\n저장: example_outputs/interview.wav ({len(allpcm)/48000:.0f}초), interview.json, report.html")
    print(f"총 {time.time()-t0:.0f}초 소요\n")

asyncio.run(main())
