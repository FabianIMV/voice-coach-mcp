# English pronunciation: reading `assess_pronunciation` and correcting

## How to request the assessment

- Pass the **exact text** to be read in `expected_text`, and show it to the user before recording.
- It works better with full sentences of 5–15 words than with isolated words. For minimal pairs,
  build a sentence: "I said ship, not sheep".
- **Limitation**: the model uses context and sometimes "fixes" an error when the correct word is
  very likely (e.g. it hears *think* although *sink* was said). Alternate with sentences whose
  words are hard to predict from context.
- A trilled Spanish-style r is not flagged (it is treated as /ɹ/), and aspiration of /p t k/ is not
  measured. If you hear it as a problem, mention it as an observation, not as data.

## Reading

- `overall_score`: ≥ 90 very good · 75–90 understandable with occasional errors · < 75 work focus.
- `frequent_confusions`: the most useful pattern. A repeated confusion (θ → s ×3) is worth more
  than an isolated error.
- `words[].errors`:
  - `substitution`: a different phoneme was said.
  - `deletion`: a phoneme is missing. Typical in final consonant clusters: *asked*, *first*, *-ed*.
  - `insertion`: an extra phoneme. Typical for Spanish speakers: an *e* before *s* + consonant, *(e)school*.
- `missing: true`: the word was not said or nothing was understood.

## Typical errors (many come from the learner's first language)

The table lists the most common ones for Spanish speakers, which also show up for speakers of
Portuguese, Italian and other languages without these sounds.

| Expected → detected | Example | How to articulate it | Minimal pairs |
|---|---|---|---|
| θ → s / t | *think* → sink/tink | Tongue tip between the teeth, blow air, no voice | think/sink, thick/sick, three/tree, path/pass |
| ð → d | *this* → dis | Tongue between the teeth **with voice** (the throat vibrates) | they/day, then/den, breathe/breed |
| v → b | *very* → berry | Upper teeth on the lower lip, voiced; the lips do not touch | very/berry, vote/boat, van/ban |
| iː → ɪ | *sheep* → ship | /iː/ long and tense (smile); /ɪ/ short and relaxed | sheep/ship, leave/live, seat/sit, peach/pitch |
| æ → ɛ / a / ʌ | *cat* | Mouth wide open, low jaw, between *a* and *e* | cat/cut, bag/bug, hat/hut, man/men |
| ʌ → a / o | *cup* | Short, relaxed, central vowel | cup/cop, luck/lock |
| ʊ → uː | *full* → fool | Short and relaxed, lips barely rounded | full/fool, pull/pool |
| z → s | *zoo*, *eyes* | Same position as /s/ but voiced (a buzz) | zoo/sue, eyes/ice, prize/price |
| ʃ ↔ tʃ | *ship* → chip | /ʃ/ is continuous (*shhh*); /tʃ/ starts with a stop | ship/chip, wash/watch |
| dʒ → j / ʝ | *jet* → yet | A stop like /tʃ/ but voiced | jet/yet, joke/yolk, jam/yam |
| h → x | *hat* with a harsh h | Just air, no friction in the throat | hat, house, hello |
| ŋ → n | *thing* → thin | Back of the tongue against the soft palate; no *g* sound | thing/thin, sing/sin |
| *e* inserted before s + consonant | *school* → eschool | Start directly on the /s/: *sss-chool* | school, Spain, street, speak |
| dropped final consonants | *asked* → ask, *walked* → walk | Finish the word; *-ed* is /t/, /d/ or /ɪd/ | walked, played, wanted, first, months |
| unreduced vowels | *about* → *a-bout* | Unstressed syllables in /ə/ (schwa), short | about, banana, problem |

## Progression

1. Minimal pairs inside short sentences with the target phoneme.
2. Sentences with the phoneme in different positions (start, middle and end of the word).
3. Reading a short paragraph; then free speech checked with `transcribe`.
Move up a level when the target confusion drops to 0–1 in two takes in a row.
