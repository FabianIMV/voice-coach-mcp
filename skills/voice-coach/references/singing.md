# Singing: reading `analyze_pitch` and choosing exercises

## How to request the analysis

- **Without a reference**: each note is compared with the nearest equal-tempered note. Good for
  sustained notes, sirens and scales.
- **With `key`** ("C major", "A minor"): each note is compared with the nearest note of the scale.
  Good for spotting notes outside the key (e.g. an F natural in G major shows up as F#4 at −95 cents).
- **With `reference_midi`**: compares against the actual melody. The user provides the MIDI
  (exported from MuseScore, a DAW, etc.). If the MIDI has accompaniment, pass the track with `midi_track`.

## Quick reading

| Field | Rough reading |
|---|---|
| `pct_within_25_cents` | ≥ 85%: very good · 60–85%: in progress · < 60%: priority focus |
| `mean_deviation_cents` / `tendency` | A bias of ±10 cents or more is systematic: flat or sharp |
| `drift_cents` | Very negative (< −15): pitch sinks towards the end (breath or fatigue) |
| `stability` | `unstable` on long notes: lack of support; `vibrato` is normal on long notes |
| `vibrato_hz`, `vibrato_pp_cents` | Typical: 5–7 Hz and 50–150 cents peak-to-peak. > 200 cents or < 4.5 Hz: wide, slow vibrato ("wobble"); > 7.5 Hz: fast tremolo |
| `notes[].drift_cents` | The note sags or rises while it is sustained |
| `wrong_note` | A different note was sung: an interval/ear problem, not fine tuning |
| `onset` late/early | More than ±80 ms from the reference beat |
| `missed`, `extra_notes` | Melody memory, running out of breath, or ornaments and slides |
| `octave_shift` | Informational: singing an octave lower is fine if it is the person's range |

1 cent is 1/100 of a semitone. A trained ear notices 5–10 cents on sustained notes; in fast
melodies, ±25 cents usually sounds in tune.

## Problem → cue → exercise

| Measured problem | Cue | Exercise |
|---|---|---|
| **Flat** tendency, especially up high | More breath support, think of the note "from above", a brighter vowel | 5 s sustained notes from *ng* → vowel; 5-note scale rising by half steps |
| **Sharp** tendency | Usually tension or too much air pressure: release jaw and neck, less volume | Soft sirens on *oo*; the same phrase at half volume |
| **Negative drift** over the take | Air management: breathe before running out | Mark breaths in the phrase; shorter phrases |
| Note **sags while sustained** (`drift_cents` < −15) | Keep the support until the end of the note | Short *messa di voce* (crescendo-decrescendo) on that note |
| **Unstable** without vibrato | Irregular airflow | Sustained notes with a lip trill, then with a vowel, 3 × 6 s |
| **Wrong note** on an interval | Interval ear | Sing the interval alone 5 times (start note → target) and return to the phrase |
| **Late onsets** | Breathe before the beat, not on it | Phrase with a metronome; count "1-2-3-and" and come in on "and" |
| **Missed notes** | Memory or breath | Sing the phrase on *la-la*, then with the lyrics |

## Warm-ups (2–3 min, pick one by level)

- Lip trill or *ng* siren from low to high and back (3 times).
- 5-note scale (do-re-mi-fa-sol-fa-mi-re-do) on *ah* or *oo*, rising by half steps.
- A comfortable 5–8 s sustained note: a baseline for pitch accuracy and stability. Analyze it without a reference.

## Suggested progression

1. Sustained notes and scales without a reference: basic pitch and stability.
2. Scales with `key`: notes of the scale.
3. Song phrases with `reference_midi`: pitch, intervals and timing.
4. Whole song in 20–40 s sections.
