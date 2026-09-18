"""인터뷰 오케스트레이터.

인터뷰어와 응답자가 각각 Higgs Realtime 세션을 갖고, **오디오를 그대로 주고받는다.**
응답자의 발화는 운율이 측정되고, 말과 톤이 어긋나면 인터뷰어가 자동으로 파고든다.

이 루프가 이 제품의 전부다. 톤 데이터가 없으면 루프 자체가 성립하지 않는다.
"""
import asyncio, time

import config, market, signals
from session import Session

INTERVIEWER_INSTRUCTIONS = """You are a professional consumer research moderator running a \
short interview with someone who was given a product to try for free two weeks ago.

You are conducting this interview on behalf of a Korean brand founder who cannot run it \
themselves. Your job is to get honest answers, not pleasant ones.

Rules:
- You will receive directives wrapped in [ ]. NEVER read a directive aloud and never \
mention that you received one. Just speak the question naturally to the participant.
- Ask exactly ONE question at a time. Keep it under 25 words. Conversational, not formal.
- Never summarize what they said back to them. Never thank them more than once.
- Never ask about price until you are directed to.
- Speak natural American English.
"""

PROBE_DIRECTIVE = """[The participant just gave a soft, polite positive answer, but their \
tone was flat — this usually means they are being polite rather than enthusiastic. Do NOT \
say anything about their tone. Ask one specific, concrete follow-up that makes a vague \
answer impossible: ask about a specific moment, a specific part of the product, or what \
they would change. One question, under 25 words.]"""


class Recorder:
    def __init__(self):
        self.turns = []      # {speaker, text, prosody, signal, pcm, tool_calls, probe}

    def add(self, speaker, turn, signal=None, probe=False):
        self.turns.append(dict(
            speaker=speaker, text=turn.text.strip(), pcm=turn.pcm,
            prosody=turn.prosody.as_dict() if turn.prosody else None,
            signal=signal, probe=probe, tool_calls=turn.tool_calls,
            first_audio_ms=turn.first_audio_ms,
        ))


async def run(on_event=lambda *a, **k: None, live=False) -> Recorder:
    rec = Recorder()
    satisfied = None

    itv = Session("interviewer", INTERVIEWER_INSTRUCTIONS, tools=[market.TOOL_SPEC])
    if live:
        from human import HumanRespondent
        resp = HumanRespondent()
    else:
        resp = Session("respondent", config.RESPONDENT["instructions"],
                       tools=[market.TOOL_SPEC], measure=True)

    async with itv, resp:
        on_event("start", founder_brief=config.FOUNDER_BRIEF_KO)

        for step in config.GUIDE:
            if step.get("conditional_on_satisfaction") and satisfied is False:
                directive = ("[They were NOT satisfied. Do not ask what they would pay. "
                             "Instead ask what would have to change for them to buy it. "
                             "One question, under 25 words.]")
            else:
                directive = f"[Ask this now: {step['intent']}]"
                if step.get("wants_tool"):
                    directive += (" [You MUST call the lookup_competitor tool first to get "
                                  "the real current US price of the main competing sheet mask "
                                  "brands, then ask your question referencing that real price. "
                                  "Call the tool before speaking.]")

            q = await itv.say_text(directive)
            rec.add("interviewer", q)
            on_event("question", step=step["id"], text=q.text.strip(), turn=q)

            a = await resp.hear_audio(q.pcm)
            sig = signals.check_mismatch(a.text, a.prosody, config.FLAT_ENGAGEMENT)
            rec.add("respondent", a, signal=sig)
            on_event("answer", step=step["id"], text=a.text.strip(),
                     prosody=a.prosody, signal=sig, turn=a)

            await itv.listen_only(a.pcm)   # 인터뷰어도 실제 오디오로 듣는다

            # --- 톤이 트리거하는 추가 질문 -----------------------------------
            if sig["mismatch"] and step.get("probe_target"):
                on_event("probe_triggered", reason=sig["why"])

                pq = await itv.say_text(PROBE_DIRECTIVE)
                rec.add("interviewer", pq, probe=True)
                on_event("question", step=step["id"] + "_probe",
                         text=pq.text.strip(), turn=pq, probe=True)

                pa = await resp.hear_audio(pq.pcm)
                psig = signals.check_mismatch(pa.text, pa.prosody, config.FLAT_ENGAGEMENT)
                rec.add("respondent", pa, signal=psig, probe=True)
                on_event("answer", step=step["id"] + "_probe", text=pa.text.strip(),
                         prosody=pa.prosody, signal=psig, turn=pa, probe=True)

                await itv.listen_only(pa.pcm)

            if step["id"] == "satisfaction":
                # 파고든 뒤의 마지막 답을 기준으로 만족 여부를 판단한다
                last = rec.turns[-1]
                satisfied = not (last["signal"] and last["signal"]["words"]["label"]
                                 in ("negative", "hedged_positive"))
                on_event("satisfaction_decided", satisfied=satisfied)

        interviewer_tools = [t for t in rec.turns for t in t["tool_calls"]]
        on_event("done", turns=len(rec.turns), tools=len(interviewer_tools))
    return rec
