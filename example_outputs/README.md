# Example outputs

Real artifacts from an actual Undertone run. No hand-editing.

| File | What it is |
|---|---|
| `report.html` | The report the founder receives. Open it in a browser. |
| `interview.json` | Every turn with its measured prosody and the mismatch verdict |
| `interview.wav` | The full interview as it was actually spoken |
| `human_flat.wav` | A real person saying *"Yeah, it was nice. I liked it."* — politely, unenthused |
| `human_warm.wav` | **The same person, the same sentence**, said like they meant it |

## Why the last two files matter

They are the same words. Undertone scores them differently because the delivery is
different — and that difference is the entire product.

Measured with `undertone/tone.py`:

| | `human_flat.wav` | `human_warm.wav` |
|---|---|---|
| engagement | 75 | 96 |

Absolute thresholds do not work here: 75 is not a low number. What makes it a signal is
that it is **21 points below this speaker's own baseline**. That is why Undertone normalizes
against each speaker rather than against a fixed scale — see `undertone/signals.py`.

Reproduce it on your own voice:

```bash
./.venv/bin/python voice_check.py
```
