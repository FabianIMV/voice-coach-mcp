"""Texts of the MCP prompts that structure a practice session.

The prompts tell Claude the order of the session and which fields to look at; the teaching
judgment comes from Claude (or the voice-coach skill), not from the server.
"""

_RULES = """
Session rules:
- Reply in the user's language.
- At the start, call read_progress and pick up the focus of the last session; at the end, log the
  session with log_progress (date, exercise, metrics before → after, next focus).
- Ask for one recording per attempt and analyze it before giving feedback; never guess what was not measured.
- If the response has warnings or low confidence, say so and suggest repeating the take before judging.
- Give at most one focus per attempt, citing concrete numbers and moments (seconds, note, word).
- Compare each attempt with the previous one and close with the next concrete exercise.
"""


def singing_session(level: str = "intermediate", goal: str = "", reference_midi: str = "") -> str:
    reference = (
        f"Use the MIDI reference `{reference_midi}` in analyze_pitch (reference_midi argument)."
        if reference_midi
        else "There is no MIDI reference: analyze against the nearest equal-tempered note or, if the user "
        "names the key, pass it in the key argument."
    )
    return f"""Run a singing session for a {level} level.{f" User goal: {goal}." if goal else ""}

1. Warm-up (2–3 min): suggest a short exercise (sirens, sustained notes, 5-note scale) suited to
   the level. Record a comfortable sustained note with record_audio (5–8 s) and analyze it with
   analyze_pitch to get a baseline for pitch accuracy and stability.
2. Main exercise: explain what to sing and for how long. Record with record_audio
   (enough seconds + 2 s of margin). {reference}
3. Analysis: read summary.pct_within_25_cents, tendency (flat/sharp), drift_cents, stability
   (stable/vibrato/unstable) and, with a reference, wrong_notes, missed and onsets.
   Find the 1–2 notes with the largest |cents| or with a late/early onset.
4. Feedback: one concrete focus (e.g. "the E4 at 3.2 s was 35 cents flat"), why it matters and a
   practical cue to fix it.
5. Next exercise: isolate the problem (repeat the phrase, slower, or only the hard interval),
   record again and compare with the previous attempt.
{_RULES}"""


def pronunciation_session(level: str = "intermediate", focus: str = "") -> str:
    return f"""Run an English (en-US) pronunciation session for a {level} level.{f" Requested focus: {focus}." if focus else ""}

1. Warm-up: 2–3 minimal pairs related to the focus (e.g. ship/sheep, think/sink). Ask the user
   to read them aloud, record with record_audio and assess with assess_pronunciation passing the
   exact text in expected_text.
2. Main exercise: one or two short sentences containing the target phonemes. Record and assess.
3. Analysis: check the overall score, the lowest-scoring words and the error type
   (substitution expected→detected, deletion, insertion). If confidence is low or text_mismatch
   appears, ask the user to repeat reading exactly the text.
4. Feedback: one phoneme per attempt; describe how it is articulated (tongue, lips, voicing) and
   contrast it with the phoneme that was detected.
5. Next exercise: more minimal pairs or a new sentence with that phoneme; measure again and compare.
{_RULES}"""


def speaking_session(context: str = "", target_duration_s: int = 60) -> str:
    return f"""Run a public-speaking session.{f" Context: {context}." if context else ""} Target length of each take: {target_duration_s} s.

1. Warm-up: breathing and a short read-aloud (20–30 s). Record it and run speech_metrics for a
   baseline of pace, pauses and pitch/volume variation.
2. Main exercise: ask the user to talk about the topic for ~{target_duration_s} s. Record with
   record_audio and analyze with speech_metrics (language of the speech).
3. Analysis: words_per_minute, long pauses (with timestamps), fillers per minute and which ones,
   pitch variation (monotone) and volume variation. Use the transcript to locate the moments.
4. Feedback: one focus per take (e.g. "6 'um' in 60 s, mostly when starting a new idea"), with a
   concrete technique to fix it.
5. Next exercise: repeat the same content applying the focus, and compare the metrics.
{_RULES}"""
