#!/usr/bin/env python3
"""Undertone web server. The browser holds the respondent; Python runs the interview."""
import asyncio, base64, functools, http.server, json, os, socketserver, sys, threading, time, wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "undertone"))

import websockets

import config, interview, report
from webrespondent import WebRespondent

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "example_outputs")
WEB = os.path.join(HERE, "web")
AUDIO = os.path.join(WEB, "audio")
HTTP_PORT, WS_PORT = 8000, 8765


def serve_static():
    h = functools.partial(http.server.SimpleHTTPRequestHandler,
                          directory=os.path.join(HERE, "web"))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", HTTP_PORT), h) as s:
        s.serve_forever()


async def handler(ws):
    resp = WebRespondent(ws)
    running = False

    async def pump():
        nonlocal running
        async for raw in ws:
            m = json.loads(raw)
            if m["type"] == "start" and not running:
                running = True
                # Clear the previous result so the report page starts empty and visibly
                # fills in the moment this interview finishes.
                old = os.path.join(WEB, "session.json")
                if os.path.exists(old):
                    os.remove(old)
                asyncio.create_task(run_interview(ws, resp))
            elif m["type"] == "answer_audio":
                await resp.inbox.put(base64.b64decode(m["audio"]))

    await pump()


async def run_interview(ws, resp):
    async def send(kind, **kw):
        turn = kw.pop("turn", None)
        pr = kw.pop("prosody", None)
        payload = {"type": kind, **{k: v for k, v in kw.items() if k != "step"}}
        if "step" in kw:
            payload["step"] = kw["step"]
        if pr:
            payload["prosody"] = pr.as_dict()
        if turn is not None and kind == "question":
            payload["latency_ms"] = turn.first_audio_ms
            payload["tool_calls"] = turn.tool_calls
        if turn is not None and kind == "answer":
            payload["tool_calls"] = turn.tool_calls
        if kind == "start":
            payload.update(product=config.PRODUCT,
                           respondent="live participant")
        await ws.send(json.dumps(payload, ensure_ascii=False, default=str))

    loop = asyncio.get_running_loop()

    def on_event(kind, **kw):
        asyncio.run_coroutine_threadsafe(send(kind, **kw), loop)

    try:
        rec = await interview.run(on_event, respondent=resp)
        os.makedirs(OUT, exist_ok=True)
        os.makedirs(AUDIO, exist_ok=True)
        for f in os.listdir(AUDIO):
            os.remove(os.path.join(AUDIO, f))

        # Save each turn separately so the founder can play back the actual voice
        for n, t in enumerate(rec.turns):
            if not t["pcm"]:
                continue
            fn = f"{n:02d}_{t['speaker']}.wav"
            with wave.open(os.path.join(AUDIO, fn), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(t["pcm"])
            t["audio"] = f"audio/{fn}"

        allpcm = b"".join(t["pcm"] for t in rec.turns)
        with wave.open(f"{OUT}/interview.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(allpcm)

        await ws.send(json.dumps({"type": "generating_report"}))
        parts = await report.build(rec, f"{OUT}/report.html")

        payload = {
            "product": config.PRODUCT,
            "brief_ko": config.FOUNDER_BRIEF_KO,
            "generated_at": time.strftime("%Y-%m-%d %H:%M"),
            "verdict": parts[0],
            "actions": parts[1],
            "limits": parts[2],
            "turns": [{k: v for k, v in t.items() if k != "pcm"} for t in rec.turns],
        }
        with open(os.path.join(WEB, "session.json"), "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        with open(f"{OUT}/interview.json", "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

        await ws.send(json.dumps({"type": "report_ready"}))
    except Exception as e:
        await ws.send(json.dumps({"type": "error", "message": f"{type(e).__name__}: {e}"}))


async def main():
    threading.Thread(target=serve_static, daemon=True).start()
    print(f"\n  \033[1mUndertone\033[0m")
    print(f"  open  \033[36mhttp://localhost:{HTTP_PORT}\033[0m            (interview)")
    print(f"  open  \033[36mhttp://localhost:{HTTP_PORT}/report.html\033[0m  (founder report)\n")
    async with websockets.serve(handler, "localhost", WS_PORT, max_size=None):
        await asyncio.Future()


asyncio.run(main())
