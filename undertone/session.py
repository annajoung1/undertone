"""A Higgs Realtime session. The interviewer holds one; a simulated respondent holds another.

Audio is passed between them as audio. It is never transcribed and handed over as text.
That is the premise of the product: the moment it becomes text, the delivery is gone.
"""
import asyncio, base64, json, os, time
from dataclasses import dataclass, field

import websockets

import market, tone

URL = "wss://api.boson.ai/v1/realtime?model=higgs-realtime"
SR = 24000
CHUNK = SR * 2 // 5          # 0.2s


@dataclass
class Turn:
    speaker: str
    text: str = ""
    pcm: bytes = b""
    tool_calls: list = field(default_factory=list)
    prosody: object = None
    first_audio_ms: int = 0

    @property
    def words(self):
        return len(self.text.split())


class Session:
    def __init__(self, speaker, instructions, tools=None, measure=False):
        self.speaker = speaker
        self.instructions = instructions
        self.tools = tools or []
        self.measure = measure          # only the respondent side gets measured
        self.ws = None

    async def __aenter__(self):
        self.ws = await websockets.connect(
            URL,
            additional_headers={"Authorization": f"Bearer {os.environ['BOSON_API_KEY']}"},
            max_size=None, open_timeout=30,
        )
        sess = {
            "model": "higgs-realtime",
            "instructions": self.instructions,
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": SR}, "turn_detection": None},
                "output": {"voice": "default"},
            },
        }
        if self.tools:
            sess["tools"] = self.tools
            sess["tool_choice"] = "auto"
        await self._send({"type": "session.update", "session": sess})
        return self

    async def __aexit__(self, *a):
        if self.ws:
            await self.ws.close()

    async def _send(self, obj):
        await self.ws.send(json.dumps(obj))

    async def say_text(self, text: str) -> Turn:
        """Give a directive, get speech back. Used to tell the interviewer what to ask."""
        await self._send({"type": "conversation.item.create", "item": {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": text}]}})
        return await self._collect()

    async def hear_audio(self, pcm: bytes) -> Turn:
        """Hear the other side's raw audio and respond. Nothing is transcribed."""
        for i in range(0, len(pcm), CHUNK):
            await self._send({"type": "input_audio_buffer.append",
                              "audio": base64.b64encode(pcm[i:i + CHUNK]).decode()})
        await self._send({"type": "input_audio_buffer.commit"})
        return await self._collect()

    async def listen_only(self, pcm: bytes):
        """Add the other side's audio to context without generating a reply.

        This is how the interviewer hears an answer. It receives the audio itself and
        never the transcript, which is what lets the follow-up decision be made on
        delivery rather than on words alone.
        """
        for i in range(0, len(pcm), CHUNK):
            await self._send({"type": "input_audio_buffer.append",
                              "audio": base64.b64encode(pcm[i:i + CHUNK]).decode()})
        await self._send({"type": "input_audio_buffer.commit"})

    async def _collect(self, _depth=0) -> Turn:
        t0 = time.time()
        await self._send({"type": "response.create"})
        t = Turn(self.speaker)
        audio, pending, first = bytearray(), {}, None

        while True:
            ev = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=90))
            ty = ev.get("type", "")
            if ty == "response.output_audio.delta":
                if first is None:
                    first = time.time()
                audio += base64.b64decode(ev["delta"])
            elif ty == "response.output_audio_transcript.delta":
                t.text += ev.get("delta", "")
            elif ty == "response.function_call_arguments.done":
                pending[ev.get("call_id")] = (ev.get("name"), ev.get("arguments", "{}"))
            elif ty == "response.output_item.done":
                it = ev.get("item", {})
                if it.get("type") == "function_call" and it.get("call_id") not in pending:
                    pending[it["call_id"]] = (it.get("name"), it.get("arguments", "{}"))
            elif ty == "error":
                t.text += f"[error: {ev.get('error', {}).get('message', '')[:100]}]"
                break
            elif ty == "response.done":
                break

        t.pcm = bytes(audio)
        t.first_audio_ms = int(((first or time.time()) - t0) * 1000)

        if pending and _depth < 2:
            for call_id, (name, raw) in pending.items():
                try:
                    args = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    args = {}
                res = market.lookup_competitor(args.get("query", ""))
                t.tool_calls.append({"name": name, "args": args, "result": res})
                await self._send({"type": "conversation.item.create", "item": {
                    "type": "function_call_output", "call_id": call_id,
                    "output": json.dumps(res)}})
            nxt = await self._collect(_depth + 1)
            nxt.tool_calls = t.tool_calls + nxt.tool_calls
            if not nxt.pcm:
                nxt.pcm = t.pcm
            return nxt

        if self.measure and t.pcm:
            t.prosody = tone.analyze(t.pcm, max(t.words, 1))
        return t
