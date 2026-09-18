"""브라우저를 응답자로 쓰는 어댑터.

Session / HumanRespondent 와 동일한 인터페이스(hear_audio -> Turn)를 제공하므로
오케스트레이터는 응답자가 어디에 있는지 몰라도 된다.
"""
import asyncio, base64, json

import tone
from human import _transcribe
from session import Turn

SR = 24000


class WebRespondent:
    speaker = "respondent"

    def __init__(self, ws):
        self.ws = ws
        self.inbox = asyncio.Queue()

    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass

    async def hear_audio(self, question_pcm: bytes) -> Turn:
        # 질문 오디오를 브라우저로 보내 재생시키고, 답변 녹음을 기다린다
        await self.ws.send(json.dumps({
            "type": "listen",
            "audio": base64.b64encode(question_pcm).decode() if question_pcm else "",
        }))
        pcm = await self.inbox.get()

        t = Turn("respondent")
        t.pcm = pcm
        t.text = await asyncio.to_thread(_transcribe, pcm) if pcm else ""
        if pcm:
            t.prosody = tone.analyze(pcm, max(len(t.text.split()), 1))
        return t

    async def listen_only(self, pcm):
        pass
