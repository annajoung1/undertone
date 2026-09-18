# Undertone

**AI interviews your US customers in English, then tells you in Korean what they actually meant — not just what they said.**

Higgs Audio Hackathon 2026 · Track: Breaking the Language Barrier

---

## The problem

Korean consumer brands want to test products in the US before committing. Flying over is
expensive. Agencies are costly and hard to trust. Founders want to run the interviews
themselves — and can't. They don't have the time, and they don't speak English well enough
to catch what a customer is really saying.

**Translation solves words. It doesn't solve nuance.**

A founder can get a perfect translation of *"yeah, it was nice"* and completely miss that it
was a rejection. That gap is where US launches die.

## What Undertone does

```
Founder briefs it in Korean
        ↓
Interviews a seeded customer in English  (Higgs Realtime, speech-to-speech)
        ↓
Measures HOW they said it, not just what  (prosody straight off the audio)
        ↓
Digs deeper when words and tone disagree  (tone triggers the follow-up)
        ↓
Reports back in Korean
```

## Why this needs Higgs specifically

This is the part that matters. Undertone measures **prosody directly from the audio Higgs
Realtime produces and receives** — pitch range, speaking rate, pause ratio — and feeds that
measurement back into the agent's behavior.

| | |
|---|---|
| **Speech-to-speech, not a pipeline** | The interviewer's audio goes straight into the respondent's ears as audio. Nothing is transcribed in between. |
| **Tone is the control signal** | When a respondent's words are positive but their delivery is flat, Undertone automatically asks a harder follow-up. |
| **Korean in, English out, Korean back** | One model, one session. The founder never leaves Korean. |
| **Measured latency: 461–929 ms** | Fast enough that the interviewer can follow up without the conversation going dead. |

**A speech-to-text pipeline cannot do this.** By the time text arrives, the tone is gone —
and the tone was the signal.

## The measurement

`undertone/tone.py` computes, per response, from raw 24 kHz PCM:

| Metric | What it is |
|---|---|
| `pitch_range_st` | 10th–90th percentile F0 spread in semitones (autocorrelation-based) |
| `speech_rate_wps` | Words per second over total duration |
| `pause_ratio` | Fraction of frames below an adaptive silence threshold |
| `engagement` | Weighted composite: pitch 55%, rate 25%, pause 20% |

Pitch range carries the most weight because F0 variability is the most stable prosodic
correlate of engagement, and because it was the only metric that separated reliably in our
own measurements (15.1 st when instructed to sound excited vs 7.5 st when instructed to
sound bored).

**Undertone does not claim to detect emotion.** It reports two independent observations —
what the words say, and what the delivery measures — and flags only where they disagree.
It then resolves the disagreement by asking, not by guessing. See `undertone/signals.py`.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install websockets sounddevice numpy
export BOSON_API_KEY=your_key_here          # never commit this
export TAVILY_API_KEY=your_key_here         # optional, for live competitor pricing
```

## Run

```bash
# Simulated respondent — full pipeline, no microphone needed
./.venv/bin/python main.py

# Play the audio out loud as it runs
./.venv/bin/python main.py --play

# LIVE: you are the respondent, answering into a microphone
./.venv/bin/python main.py --live

# Check that the tone engine separates your own voice
./.venv/bin/python voice_check.py
```

Outputs land in `example_outputs/`: `interview.wav`, `interview.json`, `report.html`.

## Example inputs and outputs

| File | What it is |
|---|---|
| `example_outputs/interview.wav` | Full interview audio as it was actually spoken |
| `example_outputs/interview.json` | Every turn with its measured prosody and mismatch verdict |
| `example_outputs/report.html` | The Korean report the founder receives |

## Honest limits

- The demo respondent is **simulated**, because we could not recruit real seeded US customers
  during a one-day hackathon. In production the respondent is a real person who was sent the
  product. `main.py --live` runs exactly that path against a real microphone.
- Higgs Realtime's TTS does not vary its delivery much on instruction (we measured a 37-point
  engagement spread across explicit style prompts, and the ordering was not reliable). The
  prosody signal is therefore far more meaningful on **real human speech** than on synthesized
  speech. This is a limitation of demoing with a simulated respondent, not of the method.
- One respondent is not a sample. Undertone is built to pre-screen messages cheaply before a
  brand spends on real research — not to replace it.
- Competitor prices fall back to a curated table of real 2026 US retail prices when no Tavily
  key is present. The report always states which source was used.

## Layout

```
main.py                 CLI and terminal UI
voice_check.py          validates the tone engine against your own voice
undertone/
  config.py             scenario: product, founder brief, interview guide, respondent
  session.py            Higgs Realtime session wrapper (audio in, audio out, tool calls)
  interview.py          orchestrator — runs the interview, triggers probes from tone
  tone.py               prosody measurement from raw PCM
  signals.py            word/tone mismatch detection
  market.py             competitor price lookup (Tavily, or curated fallback)
  human.py              real human respondent via microphone + higgs-stt-3.1
  report.py             Korean report generation and HTML rendering
```

Built with Higgs Realtime (conversation and analysis) and higgs-stt-3.1 (transcription of
human speech).
