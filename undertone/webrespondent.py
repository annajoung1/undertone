"""Adapter that puts the respondent in a browser.

Same interface as Session and HumanRespondent (hear_audio -> Turn), so the orchestrator
does not care where the person on the other side actually is.
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
        # send the question audio to the browser, then wait for the recorded answer
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
