"""진짜 사람 응답자. 인터뷰어 질문을 스피커로 들려주고, 마이크로 답을 받는다.

시뮬레이션 응답자와 동일한 인터페이스(hear_audio -> Turn)를 제공하므로
오케스트레이터는 상대가 사람인지 AI인지 몰라도 된다.
"""
import io, json, os, re, urllib.request, wave

import numpy as np
import sounddevice as sd

import tone
from session import Turn

SR = 24000


def _transcribe(pcm: bytes) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
    body, boundary = [], "----undertone"
    def part(name, val, fn=None, ctype=None):
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if fn: head += f'; filename="{fn}"'
        head += "\r\n"
        if ctype: head += f"Content-Type: {ctype}\r\n"
        body.append(head.encode() + b"\r\n" + (val if isinstance(val, bytes) else val.encode()) + b"\r\n")
    part("file", buf.getvalue(), "a.wav", "audio/wav")
    part("model", "higgs-stt-3.1")
    part("language", "en")          # 중국어로 잘못 전사되는 것 방지
    part("response_format", "json")
    body.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        "https://api.boson.ai/v1/audio/transcriptions", data=b"".join(body),
        headers={"Authorization": f"Bearer {os.environ['BOSON_API_KEY']}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            txt = json.loads(r.read()).get("text", "").strip()
        # 한자/가나가 섞여 오면 전사가 언어를 오인한 것 — 버린다
        if txt and re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", txt):
            txt = re.sub(r"[\u3040-\u30ff\u4e00-\u9fff]+", "", txt).strip()
        return txt
    except Exception as e:
        print(f"  [STT 실패] {type(e).__name__}: {e}", flush=True)
        return ""


class HumanRespondent:
    """마이크 앞의 실제 사람."""
    speaker = "respondent"

    def __init__(self, max_seconds=25):
        self.max = max_seconds

    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass

    async def hear_audio(self, question_pcm: bytes) -> Turn:
        if question_pcm:
            sd.play(np.frombuffer(question_pcm, dtype="<i2"), SR); sd.wait()

        input("\n  \033[1m[Enter] 답변 시작\033[0m")
        frames = []
        stream = sd.InputStream(samplerate=SR, channels=1, dtype="int16")
        stream.start()
        print("  \033[31m🔴 녹음중\033[0m — 끝나면 [Enter]")
        import threading
        stop = threading.Event()
        threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()
        while not stop.is_set() and len(frames) * 1024 / SR < self.max:
            d, _ = stream.read(1024); frames.append(d)
        stream.stop(); stream.close()

        pcm = np.concatenate(frames).tobytes() if frames else b""
        t = Turn("respondent")
        t.pcm = pcm
        t.text = _transcribe(pcm) if pcm else ""
        if pcm:
            t.prosody = tone.analyze(pcm, max(len(t.text.split()), 1))
        return t

    async def listen_only(self, pcm): pass
