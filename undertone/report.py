"""대표에게 가는 한국어 리포트.

측정값(운율)은 계산으로, 서술은 Higgs 텍스트 모드로 만든다.
숫자는 절대 모델이 만들지 않는다 — 측정된 값만 들어간다.
"""
import asyncio, html, json, os, re, time

import websockets

import config

URL = "wss://api.boson.ai/v1/realtime?model=higgs-realtime"


async def _ask_text(instructions: str, prompt: str, timeout=90) -> str:
    async with websockets.connect(
        URL, additional_headers={"Authorization": f"Bearer {os.environ['BOSON_API_KEY']}"},
        max_size=None, open_timeout=30) as ws:
        await ws.send(json.dumps({"type": "session.update", "session": {
            "model": "higgs-realtime", "output_modalities": ["text"],
            "instructions": instructions}}))
        await ws.send(json.dumps({"type": "conversation.item.create", "item": {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": prompt}]}}))
        await ws.send(json.dumps({"type": "response.create"}))
        out = []
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            t = ev.get("type", "")
            if "text.delta" in t:
                out.append(ev.get("delta", ""))
            elif t == "error":
                return ""
            elif t == "response.done":
                break
        return "".join(out).strip()


def _transcript_block(turns):
    lines = []
    for t in turns:
        if not t["text"]:
            continue
        who = "Interviewer" if t["speaker"] == "interviewer" else "Respondent"
        eng = (t.get("prosody") or {}).get("engagement")
        tag = f" [tone engagement {eng}/100]" if eng is not None else ""
        lines.append(f"{who}: {t['text']}{tag}")
    return "\n".join(lines)


_FOREIGN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\u0400-\u04ff]+")


def _clean(t: str) -> str:
    """모델이 간혹 섞는 일본어/중국어/키릴 문자를 제거한다."""
    return _FOREIGN.sub("", t)


async def build(rec, path):
    turns = rec.turns
    mismatches = [t for t in turns if t.get("signal") and t["signal"]["mismatch"]]
    answers = [t for t in turns if t["speaker"] == "respondent" and t["text"]]
    tools = [tc for t in turns for tc in t["tool_calls"]]

    # 번역과 종합 판단을 동시에 돌린다 (순차로 하면 두 배 걸린다)
    ko_task = _ask_text(
        "You clean up verbatim consumer research answers. Fix transcription errors and "
        "obvious mis-hearings. Output ENGLISH ONLY — if an answer came back in another "
        "language it was mis-transcribed, so render it in natural American English. "
        "Do not add, remove or soften anything the person said. "
        "Output ONLY a JSON array of strings, same order, same count. No prose.",
        json.dumps([t["text"] for t in answers], ensure_ascii=False))

    verdict_task = _ask_text(
        "You write consumer research findings for a brand founder deciding whether to "
        "launch in the US.\n"
        "HARD RULES:\n"
        "- Write ONLY in English. Plain, direct, no consultant filler.\n"
        "- This was ONE respondent. Never write 'consumers' or any plural. Write "
        "'the participant'.\n"
        "- Quote the participant's actual words when you make a claim.\n"
        "- Be specific and concrete. No generic advice like 'revisit your pricing strategy'.\n"
        "- Never invent numbers. Only use numbers given to you.\n"
        "\n"
        "Output ONLY valid JSON, no markdown fence, with exactly these keys:\n"
        '{"verdict": "one sentence — the single most important thing the founder needs to '
        'know, leading with the product problem", "actions": ["three concrete next actions, '
        'each naming a specific thing to change, test or decide"], "limits": "one sentence — '
        'what this interview could not tell them"}',
        f"Product: {config.PRODUCT['item']} at ${config.PRODUCT['price_being_tested_usd']} "
        f"for a 10-pack, seeded 2 weeks.\n"
        f"Founder asked (Korean): {config.FOUNDER_BRIEF_KO}\n"
        f"Tone-word mismatches detected: {len(mismatches)}\n"
        f"Competitor prices looked up: {json.dumps(tools, ensure_ascii=False)[:500]}\n\n"
        f"Transcript with measured tone scores:\n{_transcript_block(turns)}")

    ko, verdict = await asyncio.gather(ko_task, verdict_task)

    try:
        ko_list = json.loads(ko[ko.index("["):ko.rindex("]") + 1])
    except Exception:
        ko_list = [""] * len(answers)
    if len(ko_list) != len(answers):
        ko_list = (ko_list + [""] * len(answers))[:len(answers)]
    for t, k in zip(answers, ko_list):
        t["ko"] = _clean(k)

    try:
        v = json.loads(verdict[verdict.index("{"):verdict.rindex("}") + 1])
        parts = [_clean(str(v.get("verdict", ""))),
                 [_clean(str(a)) for a in v.get("actions", [])][:3],
                 _clean(str(v.get("limits", "")))]
    except Exception:
        # JSON 이 깨지면 줄 단위로라도 건져낸다
        lines = [l.strip() for l in (verdict or "").splitlines() if l.strip()]
        acts = [l.lstrip("-•* ").strip() for l in lines if l.lstrip().startswith(("-", "•", "*"))]
        rest = [l for l in lines if not l.lstrip().startswith(("-", "•", "*"))]
        parts = [_clean(rest[0]) if rest else "", [_clean(a) for a in acts][:3],
                 _clean(rest[-1]) if len(rest) > 1 else ""]

    _html(rec, turns, mismatches, tools, parts, path)
    return parts


def _gauge(v):
    col = "#16a34a" if v >= 67 else ("#d97706" if v >= config.FLAT_ENGAGEMENT else "#dc2626")
    return (f'<div class="g"><div class="gb" style="width:{v}%;background:{col}"></div></div>'
            f'<span class="gv" style="color:{col}">{v}</span>')


def _html(rec, turns, mismatches, tools, parts, path):
    p = config.PRODUCT
    rows = []
    for t in turns:
        if not t["text"]:
            continue
        if t["speaker"] == "interviewer":
            cls = "probe" if t.get("probe") else "q"
            lbl = "추가 질문 (톤이 발동)" if t.get("probe") else "질문"
            rows.append(f'<div class="turn {cls}"><div class="lbl">{lbl}</div>'
                        f'<div class="en">{html.escape(t["text"])}</div></div>')
        else:
            pr = t.get("prosody") or {}
            sg = t.get("signal") or {}
            warn = (f'<div class="warn">⚠ 말과 톤이 어긋남 — {html.escape(sg.get("why",""))}</div>'
                    if sg.get("mismatch") else "")
            met = ""
            if pr:
                met = (f'<div class="m">{_gauge(pr["engagement"])}'
                       f'<span class="mm">피치폭 {pr["pitch_range_st"]} st · '
                       f'속도 {pr["speech_rate_wps"]} w/s · 휴지 {int(pr["pause_ratio"]*100)}%</span></div>'
                       f'<div class="rd">{html.escape(sg.get("reading",""))}</div>')
            rows.append(f'<div class="turn a"><div class="lbl">답변</div>'
                        f'<div class="en">{html.escape(t["text"])}</div>'
                        f'<div class="ko">{html.escape(t.get("ko",""))}</div>{met}{warn}</div>')

    tool_html = ""
    if tools:
        items = []
        for tc in tools:
            for r in tc["result"]["results"][:3]:
                items.append(f'<li>{html.escape(str(r.get("product", r.get("title",""))))} '
                             f'— <b>${r.get("us_price_usd","?")}</b></li>')
        tool_html = (f'<div class="card"><h2>대화 중 조회된 실제 경쟁 가격</h2>'
                     f'<ul class="tl">{"".join(items)}</ul>'
                     f'<div class="src">출처: {html.escape(tools[0]["result"]["source"])}</div></div>')

    doc = f"""<!doctype html><meta charset="utf-8">
<title>Undertone — 인터뷰 리포트</title>
<style>
:root{{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--line:#e7e5e4;--card:#fff}}
*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.65 -apple-system,BlinkMacSystemFont,"Pretendard","Apple SD Gothic Neo",sans-serif;
background:var(--bg);color:var(--fg)}}
.wrap{{max-width:760px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}}
.sub{{color:var(--mut);font-size:13px;margin-bottom:28px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin-bottom:16px}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:0 0 12px;font-weight:600}}
.lead{{font-size:19px;line-height:1.5;font-weight:600;letter-spacing:-.01em}}
.acts{{margin:0;padding-left:0;list-style:none}}
.acts li{{padding:7px 0 7px 18px;border-bottom:1px solid var(--line);position:relative}}
.acts li:last-child{{border:0}}
.acts li:before{{content:"";position:absolute;left:2px;top:15px;width:5px;height:5px;border-radius:50%;background:#dc2626}}
.limit{{color:var(--mut);font-size:13.5px;border-left:2px solid var(--line);padding-left:12px}}
.turn{{padding:14px 0;border-bottom:1px solid var(--line)}}
.turn:last-child{{border:0}}
.lbl{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);margin-bottom:5px}}
.q .lbl{{color:#0369a1}} .probe .lbl{{color:#9333ea;font-weight:700}}
.probe{{background:#faf5ff;margin:0 -12px;padding:14px 12px;border-radius:8px}}
.en{{font-size:14.5px}} .ko{{color:var(--mut);font-size:13.5px;margin-top:3px}}
.m{{display:flex;align-items:center;gap:10px;margin-top:10px}}
.g{{width:130px;height:6px;background:var(--line);border-radius:3px;overflow:hidden}}
.gb{{height:100%}} .gv{{font-weight:700;font-size:13px;min-width:26px}}
.mm{{font-size:11.5px;color:var(--mut)}}
.rd{{font-size:12.5px;color:var(--mut);margin-top:3px}}
.warn{{margin-top:9px;background:#fef2f2;border:1px solid #fecaca;color:#991b1b;
padding:8px 11px;border-radius:7px;font-size:13px}}
.tl{{margin:0;padding-left:18px}} .tl li{{padding:2px 0;font-size:14px}}
.src{{font-size:11.5px;color:var(--mut);margin-top:8px}}
.ft{{color:var(--mut);font-size:12px;margin-top:26px;line-height:1.7}}
@media(prefers-color-scheme:dark){{:root{{--bg:#1c1917;--fg:#fafaf9;--mut:#a8a29e;--line:#292524;--card:#231f1e}}
.probe{{background:#2a1f35}} .warn{{background:#2a1416;border-color:#7f1d1d;color:#fca5a5}}}}
</style>
<div class="wrap">
<h1>인터뷰 리포트</h1>
<div class="sub">{html.escape(p['item'])} · ${p['price_being_tested_usd']} / 10장 ·
{html.escape(p['seeded_for'])} 시딩 · 응답자 1명 · {time.strftime('%Y-%m-%d %H:%M')}</div>

<div class="card"><h2>결론</h2><div class="lead">{html.escape(parts[0])}</div></div>

<div class="card"><h2>그래서 뭘 해야 하나</h2>
<ul class="acts">{''.join(f'<li>{html.escape(a)}</li>' for a in parts[1])}</ul></div>

{tool_html}

<div class="card"><h2>인터뷰 전문 · 톤 측정</h2>{''.join(rows)}</div>

<div class="card"><h2>이 인터뷰가 알려주지 못하는 것</h2>
<div class="limit">{html.escape(parts[2])}</div></div>

<div class="ft">
톤 점수는 응답 오디오에서 직접 측정한 운율 지표입니다 — 피치 변동폭(55%), 발화 속도(25%), 휴지 비율(20%).
감정을 단정하지 않고, 말한 내용과 어긋나는 지점만 표시합니다.<br>
Undertone · 측정 Higgs Realtime · 전사 higgs-stt-3.1
</div>
</div>"""
    with open(path, "w") as f:
        f.write(doc)
