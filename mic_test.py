"""최고 리스크 검증: 마이크로 한국어 말하기 -> 페르소나가 영어 음성으로 응답."""
import asyncio, base64, json, os, wave
import numpy as np, sounddevice as sd, websockets

URL = "wss://api.boson.ai/v1/realtime?model=higgs-realtime"
KEY = os.environ["BOSON_API_KEY"]
SR = 24000
SECONDS = 6

INSTR = ("You are Maya, 24, a skincare shopper in LA who browses #skintok. "
         "You may be spoken to in Korean, but you ALWAYS reply in casual American English. "
         "Be honest and specific. Keep it under 3 sentences.")


async def main():
    print(f"\n🎤 {SECONDS}초간 한국어로 말하세요. 예: '저희 시카 나이트 세럼 38달러인데 어떠세요?'")
    print("   3..2..1.. 시작!\n")
    rec = sd.rec(int(SECONDS * SR), samplerate=SR, channels=1, dtype="int16")
    sd.wait()
    pcm = rec.tobytes()
    rms = float(np.sqrt(np.mean(rec.astype(np.float32) ** 2)))
    print(f"녹음 완료. RMS={rms:.0f} ({'소리 감지됨' if rms > 200 else '⚠️ 너무 조용함'})")

    audio, text, in_tx = bytearray(), [], []
    async with websockets.connect(URL, additional_headers={"Authorization": f"Bearer {KEY}"},
                                  max_size=None, open_timeout=30) as ws:
        await ws.send(json.dumps({"type": "session.update", "session": {
            "model": "higgs-realtime",
            "instructions": INSTR,
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": SR}, "turn_detection": None},
                "output": {"voice": "default"},
            },
        }}))
        # 마이크 오디오를 청크로 올린다
        CH = SR * 2 // 5  # 0.2초
        for i in range(0, len(pcm), CH):
            await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                      "audio": base64.b64encode(pcm[i:i + CH]).decode()}))
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await ws.send(json.dumps({"type": "response.create"}))

        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            t = ev.get("type", "")
            if t == "response.output_audio.delta":
                audio += base64.b64decode(ev["delta"])
            elif t == "response.output_audio_transcript.delta":
                text.append(ev.get("delta", ""))
            elif "input_audio_transcription" in t and "delta" in t:
                in_tx.append(ev.get("delta", ""))
            elif "input_audio_transcription.completed" in t:
                in_tx.append(ev.get("transcript", ""))
            elif t == "error":
                print("ERROR:", json.dumps(ev)[:500]); return
            elif t == "response.done":
                break

    if in_tx:
        print(f"\n[내가 말한 것] {''.join(in_tx)}")
    print(f"[Maya 응답]  {''.join(text).strip()}")

    if audio:
        with wave.open("mic_reply.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(bytes(audio))
        print(f"\n▶ 재생 중... ({len(audio)/48000:.1f}초)")
        sd.play(np.frombuffer(bytes(audio), dtype=np.int16), SR); sd.wait()

asyncio.run(main())
