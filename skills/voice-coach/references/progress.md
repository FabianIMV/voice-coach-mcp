# Progress log

The log lives in `~/VoiceCoach/progress.md` (or `$VOICE_COACH_DIR/progress.md`). It is used
through two server tools:

- `read_progress(entries=5)` at the start: returns the latest sessions as markdown.
- `log_progress(entry)` at the end: appends a section to the end of the file.

If you have direct file access (Claude Code), you may read the whole file to see long-term
trends, but always write through `log_progress` so the format stays consistent.

## Entry format

```markdown
## 2026-10-23 · Singing · C major scale (intermediate)

- **Goal**: tune the high part of the scale.
- **Takes**: 3 (`c-scale-take1` … `take3`)
- **Metrics**: within ±25 cents 62% → 88%; mean deviation −14 → −4 cents (flat → centered); B4 −42 → −12 cents.
- **What improved**: B4 and C5 no longer drop; steady vibrato on the last note (5.5 Hz).
- **Still pending**: late onsets in bar 3 (~+130 ms).
- **Next focus**: on-time onsets with a metronome; keep the high part within ±20 cents.
```

For pronunciation, log the overall score and the confusions (e.g. "θ → s: 3 → 1"). For public
speaking, log wpm, fillers/min, long pauses and pitch deviation.

## Rules

- One entry per session, at the end (not per take).
- Always with before → after numbers and the **next focus**: that is what the next session picks up.
- Keep it short: 5 to 8 bullets.
- Every 5 sessions, if the user wants, add a `## Summary …` entry with the trend: which metrics
  improved steadily and which did not change.
