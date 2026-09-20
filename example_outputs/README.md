# Example outputs

Real artifacts from an actual Undertone run. No hand-editing.

| File | What it is |
|---|---|
| `report.html` | The report the founder receives. Open it in a browser. |
| `interview.json` | Every turn with its measured prosody and the mismatch verdict |
| `interview.wav` | The full interview as it was actually spoken |
| `human_flat.wav` | A real person saying *"Yeah, it was nice. I liked it."* — politely, unenthused. 4.95s |
| `human_warm.wav` | **The same person, the same sentence**, said like they meant it. 3.11s |

## Why the last two files matter

They are the same words. Undertone scores them differently because the delivery is
different — and that difference is the entire product.

Measured with `undertone/tone.py`:

| | `human_flat.wav` | `human_warm.wav` |
|---|---|---|
| engagement | **60** | **76** |
| pitch range | 17.1 st | 12.7 st |
| speech rate | 1.41 w/s | 2.25 w/s |
| pause ratio | 42.6% | 39.8% |

Absolute thresholds do not work here: 60 is not a low number on its own. What makes it a
signal is that it sits **16 points below this speaker's own baseline**.

**Read the middle rows before trusting the top one.** On pitch range — the axis weighted most
heavily, at 55% — the flat take scores *higher*. This speaker flattens by slowing down, not by
losing pitch, so a single-axis detector would have called the flat take the livelier one. That
is the reason every answer is compared to the same speaker across several axes rather than to
one fixed scale. See `undertone/tone.py` and `undertone/signals.py`.

*Re-recorded 2026-09-19 in a quiet room. The earlier pair was captured at the hackathon venue:
the flat take ran 11.1 seconds of continuous room noise against a 2.8-second warm take, so its
reported rate — and therefore its score — was an artifact of when the recording was stopped,
not of how the line was delivered.*

Reproduce it on your own voice:

```bash
./.venv/bin/python voice_check.py
```
