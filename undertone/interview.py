"""The interview loop.

The interviewer and the respondent each hold a session and pass audio between them. Every
answer is measured for prosody, and when the words and the delivery disagree, the
interviewer automatically asks a harder follow-up.

That loop is the whole product. Without the prosody measurement there is nothing to
trigger the follow-up, and without speech-to-speech there is nothing to measure.
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
- Ask exactly ONE question. ONE sentence. ONE question mark. Under 18 words.
- If the directive seems to contain more than one question, ask only the FIRST one.
- NEVER ask two things in one turn. Never add "and also...", "as well as...", or a second
  clause that asks something new. If you are tempted to ask two things, ask the first only.
- Do not preface your question with commentary. Just ask it.
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


async def run(on_event=lambda *a, **k: None, live=False, respondent=None) -> Recorder:
    rec = Recorder()
    satisfied = None
    baseline = signals.Baseline(config.ENGAGEMENT_DROP)

    itv = Session("interviewer", INTERVIEWER_INSTRUCTIONS, tools=[market.TOOL_SPEC])
    if respondent is not None:
        resp = respondent
    elif live:
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
                             "Ask instead what would have to change for them to buy it. "
                             "ONE question, under 18 words.]")
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
            sig = signals.check_mismatch(a.text, a.prosody, baseline)
            baseline.observe(a.prosody)
            rec.add("respondent", a, signal=sig)
            on_event("answer", step=step["id"], text=a.text.strip(),
                     prosody=a.prosody, signal=sig, turn=a)

            await itv.listen_only(a.pcm)   # the interviewer hears the audio, not a transcript

            # --- the follow-up that prosody triggers ---------------------------
            if sig["mismatch"] and step.get("probe_target"):
                on_event("probe_triggered", reason=sig["why"])

                pq = await itv.say_text(PROBE_DIRECTIVE)
                rec.add("interviewer", pq, probe=True)
                on_event("question", step=step["id"] + "_probe",
                         text=pq.text.strip(), turn=pq, probe=True)

                pa = await resp.hear_audio(pq.pcm)
                psig = signals.check_mismatch(pa.text, pa.prosody, baseline)
                baseline.observe(pa.prosody)
                rec.add("respondent", pa, signal=psig, probe=True)
                on_event("answer", step=step["id"] + "_probe", text=pa.text.strip(),
                         prosody=pa.prosody, signal=psig, turn=pa, probe=True)

                await itv.listen_only(pa.pcm)

            if step["id"] == "satisfaction":
                # judge satisfaction on the last answer, i.e. after any follow-up
                last = rec.turns[-1]
                satisfied = not (last["signal"] and last["signal"]["words"]["label"]
                                 in ("negative", "hedged_positive"))
                on_event("satisfaction_decided", satisfied=satisfied)

        interviewer_tools = [t for t in rec.turns for t in t["tool_calls"]]
        on_event("done", turns=len(rec.turns), tools=len(interviewer_tools))
    return rec
