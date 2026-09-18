#!/usr/bin/env python3
"""Undertone - interviews US consumers on a founder's behalf and reads how they said it.

Run with --live to answer into a microphone yourself, or --play to hear the audio.
"""
import asyncio, json, os, sys, time, wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "undertone"))

import config, interview, report

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "example_outputs")
PLAY = "--play" in sys.argv
LIVE = "--live" in sys.argv   # a real person answers instead of a simulated one

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
        print(f"{C['dim']}Founder brief, spoken in Korean{C['r']}\n  {kw['founder_brief']}\n")
        p = config.PRODUCT
        print(f"{C['dim']}Product    {p['item']} · ${p['price_being_tested_usd']} · "
              f"seeded {p['seeded_for']}{C['r']}")
        who = "live participant (microphone)" if LIVE else f"{config.RESPONDENT['name']} (simulated)"
        print(f"{C['dim']}Respondent {who}{C['r']}")
        print(f"{C['dim']}{'─'*66}{C['r']}")

    elif kind == "question":
        tag = f"{C['mg']}▸ FOLLOW-UP{C['r']}" if kw.get("probe") else f"{C['cy']}▸ Interviewer{C['r']}"
        print(f"\n{tag}  {C['gy']}({kw['turn'].first_audio_ms}ms){C['r']}")
        print(f"  {kw['text']}")
        play(kw["turn"].pcm)

    elif kind == "answer":
        print(f"\n{C['ye']}◂ Participant{C['r']}")
        print(f"  {kw['text']}")
        play(kw["turn"].pcm)
        pr, sg = kw["prosody"], kw["signal"]
        if pr:
            print(f"\n  {C['dim']}prosody{C['r']}  {bar(pr.engagement)} {pr.engagement:>3}"
                  f"   {C['gy']}{pr.speech_rate_wps} words/s · "
                  f"pitch range {pr.pitch_range_st} st · {int(pr.pause_ratio*100)}% pause{C['r']}")
            print(f"  {C['dim']}reading{C['r']}  {sg.get('reading','') if sg else ''}")
        if sg and sg["mismatch"]:
            print(f"  {C['rd']}{C['b']}⚠  words and tone disagree{C['r']}  {sg['why']}")
        if kw["turn"].tool_calls:
            for t in kw["turn"].tool_calls:
                res = t["result"]
                print(f"  {C['gr']}🔍 lookup{C['r']} \"{t['args'].get('query','')}\" "
                      f"→ {C['gy']}{res['source']}{C['r']}")
                for h in res["results"][:3]:
                    print(f"           {C['gy']}{h.get('product', h.get('title',''))}: "
                          f"${h.get('us_price_usd','?')}{C['r']}")

    elif kind == "probe_triggered":
        print(f"\n  {C['mg']}{C['b']}↳ prosody triggered a deeper follow-up{C['r']}")

    elif kind == "satisfaction_decided":
        print(f"\n  {C['dim']}satisfied → {kw['satisfied']} (branches the next question){C['r']}")

    elif kind == "done":
        print(f"\n{C['dim']}{'─'*66}{C['r']}")
        print(f"{C['dim']}{kw['turns']} turns · {kw['tools']} tool calls{C['r']}")


async def main():
    t0 = time.time()
    rec = await interview.run(on_event, live=LIVE)
    os.makedirs(OUT, exist_ok=True)

    # Save the whole interview as one file so it can be listened to end to end
    allpcm = b"".join(t["pcm"] for t in rec.turns)
    with wave.open(f"{OUT}/interview.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(allpcm)

    data = [{k: v for k, v in t.items() if k != "pcm"} for t in rec.turns]
    with open(f"{OUT}/interview.json", "w") as f:
        json.dump({"product": config.PRODUCT, "brief_ko": config.FOUNDER_BRIEF_KO,
                   "respondent": config.RESPONDENT["label"], "turns": data},
                  f, ensure_ascii=False, indent=2)

    print(f"\n{C['dim']}writing the report...{C['r']}")
    parts = await report.build(rec, f"{OUT}/report.html")
    print(f"\n{C['b']}Verdict{C['r']}  {parts[0]}")
    for a in (parts[1] if isinstance(parts[1], list) else []):
        print(f"  {C['rd']}·{C['r']} {a}")

    print(f"\nwrote example_outputs/ — interview.wav ({len(allpcm)/48000:.0f}s), interview.json, report.html")
    print(f"{time.time()-t0:.0f}s total\n")

asyncio.run(main())
