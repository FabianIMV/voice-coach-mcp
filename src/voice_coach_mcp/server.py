"""MCP server (stdio): tool and prompt registration. The logic lives in the subpackages."""

import functools
import logging
import time

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__, progress, prompts
from .audio.recording import record
from .config import load_config
from .errors import UserError
from .output import to_json
from .pronunciation.assessment import assess
from .singing.intonation import analyze
from .speech.analysis import speech_metrics as run_speech_metrics
from .speech.analysis import transcribe_audio

log = logging.getLogger("voice_coach_mcp")

INSTRUCTIONS = """This server measures audio so you can act as a voice coach (singing, English
pronunciation and public speaking). Tools return compact JSON measurements with `confidence` and
`warnings`; the interpretation and feedback are yours. When a response includes `full_details`,
that JSON file holds every detail. Audio can be passed as a path or as the name returned by
record_audio. Reply in the user's language."""

mcp = MCPServer("voice-coach", instructions=INSTRUCTIONS, version=__version__)

# Analysis tools only write a details JSON next to the audio; none of them touch the network
# (except assess_pronunciation when the user configures the Azure backend).
_ANALYSIS = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


def _readable_errors(fn):
    """Turns UserError into ToolError so the message reaches Claude verbatim."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except UserError as e:
            raise ToolError(str(e)) from e

    return wrapper


@mcp.tool(
    annotations=ToolAnnotations(
        title="Record audio",
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    )
)
@_readable_errors
async def record_audio(seconds: float, ctx: Context, name: str | None = None) -> str:
    """Records from the computer's microphone and saves a 16 kHz mono .wav.

    Args:
        seconds: recording length (max 120 by default). Tell the user before calling.
        name: optional file name (without extension); defaults to date and time.

    Returns `audio` (path of the .wav), levels (peak/RMS in dBFS, estimated SNR, % clipping),
    `confidence` and `warnings`. The `no_microphone_permission` warning means macOS delivered no
    audio: the user must enable the microphone for the app in System Settings.
    """
    config = load_config()
    result: dict = {}

    async def record_in_thread():
        result.update(await anyio.to_thread.run_sync(record, seconds, name, config))

    start = time.monotonic()
    async with anyio.create_task_group() as tg:
        tg.start_soon(record_in_thread)
        while not result:
            elapsed = min(time.monotonic() - start, seconds)
            try:
                await ctx.report_progress(elapsed, seconds, "recording")
            except Exception:  # the client may not ask for progress
                log.debug("could not report progress", exc_info=True)
            await anyio.sleep(1.0)
    return to_json(result)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Analyze pitch accuracy", **_ANALYSIS.model_dump(exclude={"title"})
    )
)
@_readable_errors
async def analyze_pitch(
    audio: str,
    reference_midi: str | None = None,
    key: str | None = None,
    midi_track: int | None = None,
) -> str:
    """Measures the pitch accuracy of sung audio (solo voice, one melodic line).

    Args:
        audio: audio path (wav/flac/mp3/m4a) or a name returned by record_audio.
        reference_midi: optional path to a .mid with the expected melody. Tolerates singing an
            octave up/down, starting at another moment and a somewhat different tempo.
        key: optional when there is no MIDI, e.g. "A minor", "G major", "F#" (Spanish names such as
            "La menor" also work): each note is compared with the nearest note of that scale.
            Without it, with the nearest equal-tempered note.
        midi_track: index of the MIDI track to use (default: the non-drum track with most notes).

    Returns `summary` (notes, range, pct_within_25_cents, signed mean_deviation_cents,
    tendency flat/sharp/centered, drift_cents between 1st and 2nd half, stability counts; with
    MIDI also missed, extra_notes, wrong_notes, onsets on_time/late/early, octave_shift,
    start_offset_ms and relative_tempo >1 = slower) and `notes`: t (s), dur, note or
    expected/sung, cents (+ = sharp), stability (stable | vibrato with vibrato_hz and
    vibrato_pp_cents | unstable with std_cents), drift_cents within the note and, with MIDI,
    onset_ms/onset; reference notes not sung have status=missed and unmatched sung notes
    status=extra. If the list does not fit, the most problematic notes are shown and the rest
    is in `full_details`.
    """
    config = load_config()
    return await anyio.to_thread.run_sync(
        functools.partial(
            analyze, audio, config, reference_midi=reference_midi, key=key, midi_track=midi_track
        )
    )


@mcp.tool(
    annotations=ToolAnnotations(title="Transcribe audio", **_ANALYSIS.model_dump(exclude={"title"}))
)
@_readable_errors
async def transcribe(audio: str, language: str | None = None) -> str:
    """Transcribes audio with timestamps (faster-whisper, local).

    Args:
        audio: audio path or a name returned by record_audio.
        language: "en", "es", "en-US", "Spanish"…; auto-detected when omitted.

    Returns `language`, `language_prob`, `text`, `segments` [{t, end, text}] and `words`
    [{w, t, end}]. If it does not fit, words are dropped first and then segments (everything
    stays in `full_details`). The first call downloads the model (VOICE_COACH_WHISPER_MODEL).
    """
    config = load_config()
    return await anyio.to_thread.run_sync(transcribe_audio, audio, config, language)


@mcp.tool(
    annotations=ToolAnnotations(title="Speech metrics", **_ANALYSIS.model_dump(exclude={"title"}))
)
@_readable_errors
async def speech_metrics(audio: str, language: str, pause_threshold_s: float = 0.7) -> str:
    """Measures pace, pauses, filler words and pitch/volume variation of a speech.

    Args:
        audio: audio path or a name returned by record_audio.
        language: language of the speech ("en" or "es"; filler lists exist for both).
        pause_threshold_s: minimum silence between words to count as a long pause.

    Returns:
    - `pace`: words, speaking_time_s, words_per_minute, wpm_excluding_long_pauses.
    - `pauses`: count, total_s, max_s, per_minute and items [{t, dur, after: previous word}].
    - `fillers`: total, per_minute, by_type and occurrences [{t, text}]. Ambiguous words
      ("like", "so") only count when isolated by a comma or a pause.
    - `pitch`: median_f0_hz, std_semitones, range_p10_p90_semitones, monotone (std < 2 st) and
      monotone_stretches [{t, end}] over 8 s windows.
    - `volume`: mean_dbfs, std_between_words_db, range_p10_p90_db, low_variation (std < 3 dB).
    - `segments` of the transcript [{t, end, text}].
    """
    config = load_config()
    return await anyio.to_thread.run_sync(
        run_speech_metrics, audio, config, language, pause_threshold_s
    )


@mcp.tool(
    annotations=ToolAnnotations(
        title="Assess pronunciation", **_ANALYSIS.model_dump(exclude={"title"})
    )
)
@_readable_errors
async def assess_pronunciation(audio: str, expected_text: str, language: str = "en-US") -> str:
    """Compares the pronounced phonemes with the expected ones for a text read aloud (English).

    Args:
        audio: audio path or a name returned by record_audio (up to 60 s; short sentences work best).
        expected_text: the exact text that was read.
        language: "en-US" (default) or "en-GB".

    Returns `summary` (overall_score 0–100, words_with_errors, error counts by type,
    frequent_confusions expected→detected) and `words`: word, score, t (s) and, when there are
    errors, expected/detected in IPA and errors [{type: substitution|deletion|insertion,
    expected, detected}]; `missing` when the word was not said. `phonemes` holds both full
    sequences. Word score = 100·(1 − (S + D + 0.5·I)/expected phonemes). Allophonic variants
    (flap, schwa, linking r) do not count as errors. The text_mismatch warning means a
    different text was probably read. Backend: local wav2vec2, or Azure when
    VOICE_COACH_PRONUNCIATION_BACKEND=azure (then the audio is sent to Azure).
    """
    config = load_config()
    return await anyio.to_thread.run_sync(assess, audio, expected_text, config, language)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Read progress log",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
@_readable_errors
async def read_progress(entries: int = 5) -> str:
    """Reads the latest sessions from the progress log (~/VoiceCoach/progress.md).

    Use it at the start of a session to pick up the previous focus. Returns `file`,
    `total_entries` and `entries` (markdown of each session, oldest to newest).
    """
    return to_json(progress.read(load_config(), entries))


@mcp.tool(
    annotations=ToolAnnotations(
        title="Log progress",
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    )
)
@_readable_errors
async def log_progress(entry: str) -> str:
    """Appends a session to the progress log (~/VoiceCoach/progress.md).

    Args:
        entry: markdown of the session. It should start with "## YYYY-MM-DD · mode · exercise";
            if it does not start with "## ", the date and time are added as the title.
    """
    return to_json(progress.log(load_config(), entry))


@mcp.prompt()
def singing_session(level: str = "intermediate", goal: str = "", reference_midi: str = "") -> str:
    """Guides a singing session: warm-up, exercise, pitch analysis, feedback and next step."""
    return prompts.singing_session(level, goal, reference_midi)


@mcp.prompt()
def pronunciation_session(level: str = "intermediate", focus: str = "") -> str:
    """Guides an English pronunciation session with minimal pairs and target sentences."""
    return prompts.pronunciation_session(level, focus)


@mcp.prompt()
def speaking_session(context: str = "", target_duration_s: int = 60) -> str:
    """Guides a public-speaking session: pace, pauses, filler words and pitch/volume variation."""
    return prompts.speaking_session(context, target_duration_s)
