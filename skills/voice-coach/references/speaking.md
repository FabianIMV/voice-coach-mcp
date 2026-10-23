# Public speaking: reading `speech_metrics` and training

## How to request the analysis

- Takes of 45–90 s on a topic the user knows (introducing themselves, explaining their work,
  defending an idea). Pass the `language` of the speech ("en" or "es").
- To compare takes, keep the same topic and length.

## Rough ranges

| Metric | Reference |
|---|---|
| `words_per_minute` | 120–160: comfortable for presenting · > 170: fast · < 110: slow. Spanish usually measures somewhat fewer wpm than English at the same syllable rate. |
| `wpm_excluding_long_pauses` | Articulation rate: if very high (> 190) while wpm is normal, the person speaks fast and compensates with pauses |
| `pauses.items` | Pauses after an idea (after a period) help. If the word in `after` is *the*, *to*, *of*, *that*…, the pause is mid-sentence: it signals hesitation |
| `fillers.per_minute` | < 2: excellent · 2–5: normal · > 5: work focus. Check `by_type` to see which one dominates |
| `pitch.std_semitones` | < 2: monotone · 2–4: natural · > 4: very expressive. `monotone_stretches` tells you where |
| `volume.std_between_words_db` | < 3 dB: flat volume · 3–6 dB: natural · > 8 dB: big drops (inaudible sentence endings) |

Fillers are detected on the transcript: a very short "uh" may not appear, so the count is a **minimum**.

## Problem → technique → exercise

| Problem | Technique | Exercise |
|---|---|---|
| Many fillers | Replace the filler with a silent pause | Repeat the take; whenever the urge to say *um* comes, close your mouth for 1 s. Goal: −50% fillers/min |
| Mid-sentence pauses | Plan the sentence before starting it | Write 3 key ideas; speak idea by idea, pausing only between ideas |
| Too fast | Intentional pauses and marked sentence endings | Read a paragraph pausing at every period; goal 140 wpm |
| Monotone | Raise the pitch on the key word and lower it to close the idea | Read the same sentence stressing a different word each time; goal: std ≥ 2.5 semitones |
| Flat or fading volume | Project to the back of the room; keep the air until the last word | Say short sentences to an imaginary listener 3 m away; finish each sentence with the same energy |

## Progression

1. Reading aloud (a known text): pace and pauses.
2. A prepared 60 s talk: fillers and pauses.
3. 45 s improvised answers to questions Claude asks: fluency under pressure.
