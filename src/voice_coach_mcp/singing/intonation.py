"""Pitch-accuracy analysis: sung notes vs. equal temperament, a key, or a MIDI melody."""

import numpy as np

from ..audio import quality as q
from ..audio.io import load, resolve_path
from ..config import Config
from ..output import Trimmable, fit
from .pitch import Contour, Note, extract_contour, segment
from .reference import Melody, RefNote, load_melody
from .theory import note_name, parse_key, target_note

TOLERANCE_CENTS = 25
TENDENCY_CENTS = 10
WRONG_NOTE_CENTS = 50
ONSET_TOLERANCE_MS = 80
OCTAVES = (0, -1, 1, -2, 2)  # in order of preference on ties
MISSED_COST = 2.0
EXTRA_COST = 1.5


def analyze(
    audio: str,
    config: Config,
    reference_midi: str | None = None,
    key: str | None = None,
    midi_track: int | None = None,
) -> str:
    path = resolve_path(audio, config)
    y = load(path)
    quality = q.assess(y, min_duration=1.0)
    warnings = list(quality.warnings)
    result: dict = {"audio": str(path), "duration_s": quality.duration_s}

    scale, key_name = None, None
    if key and reference_midi:
        warnings.append(
            q.warning("key_ignored", "With a MIDI reference the melody is used, not the key.")
        )
    elif key:
        scale, key_name = parse_key(key)
    melody = (
        load_melody(resolve_path(reference_midi, config), midi_track) if reference_midi else None
    )

    contour = extract_contour(y, a4=config.a4_hz) if quality.factor > 0 else None
    notes = segment(contour) if contour is not None else []

    if melody:
        result["mode"] = "midi_reference"
        summary, items, alignment_factor, extra_warnings = _with_reference(notes, contour, melody)
        warnings += extra_warnings
    else:
        result["mode"] = "key" if scale else "equal_temperament"
        if key_name:
            result["key"] = key_name
        summary, items = _without_reference(notes, scale)
        alignment_factor = 1.0

    confidence = quality.factor * alignment_factor * _voicing_factor(notes)
    if contour is not None:
        voiced = float(np.mean(np.isfinite(contour.midi)))
        if voiced < 0.2 and quality.duration_s > 2:
            warnings.append(
                q.warning("low_voicing", f"Only {voiced:.0%} of the audio has a clear pitch.")
            )
    if len(notes) < 2 and quality.factor > 0:
        warnings.append(q.warning("few_notes_detected", f"{len(notes)} notes detected."))
        confidence *= 0.5

    result["summary"] = summary
    result["notes"] = items
    result["confidence"] = q.confidence(confidence)
    result["warnings"] = warnings
    return fit(
        result, audio=path, tool="pitch", config=config, trimmable=[Trimmable("notes", _priority)]
    )


def _priority(item: dict) -> float:
    if item.get("status") == "missed" or item.get("wrong_note"):
        return 1000.0
    if item.get("status") == "extra":
        return 60.0
    bonus = 50.0 if item.get("onset", "on_time") != "on_time" else 0.0
    bonus += 30.0 if item.get("stability") == "unstable" else 0.0
    return abs(item.get("cents", 0)) + bonus


def _voicing_factor(notes: list[Note]) -> float:
    if not notes:
        return 0.0
    durations = np.array([n.duration for n in notes])
    prob = float(np.average([n.voicing_prob for n in notes], weights=durations))
    return min(1.0, prob / 0.7)


def _note_item(note: Note, target: int, note_key: str = "note") -> dict:
    item = {
        "t": round(note.start, 2),
        "dur": round(note.duration, 2),
        note_key: note_name(target),
        "cents": int(round(100 * (note.midi - target))),
        "stability": note.stability,
    }
    if note.stability == "vibrato":
        item["vibrato_hz"] = round(note.vibrato_hz, 1)
        item["vibrato_pp_cents"] = int(round(note.vibrato_pp_cents))
    elif note.stability == "unstable":
        item["std_cents"] = int(round(note.std_cents))
    if abs(note.drift_cents) >= 15:
        item["drift_cents"] = int(round(note.drift_cents))
    return item


def _base_summary(
    cents: list[float], durations: list[float], times: list[float], notes: list[Note]
) -> dict:
    summary: dict = {"notes": len(notes)}
    if not notes:
        return summary
    c = np.array(cents, dtype=float)
    w = np.array(durations, dtype=float)
    mean = float(np.average(c, weights=w))
    lowest = note_name(round(min(n.midi for n in notes)))
    highest = note_name(round(max(n.midi for n in notes)))
    summary["range"] = f"{lowest}–{highest}"
    summary["pct_within_25_cents"] = round(100 * float(np.mean(np.abs(c) <= TOLERANCE_CENTS)), 1)
    summary["mean_deviation_cents"] = round(mean, 1)
    summary["mean_abs_deviation_cents"] = round(float(np.average(np.abs(c), weights=w)), 1)
    summary["tendency"] = (
        "sharp" if mean > TENDENCY_CENTS else "flat" if mean < -TENDENCY_CENTS else "centered"
    )
    if len(c) >= 4:
        order = np.argsort(times)
        half = len(order) // 2
        summary["drift_cents"] = round(
            float(np.mean(c[order[half:]]) - np.mean(c[order[:half]])), 1
        )
    summary["stability"] = {
        s: sum(n.stability == s for n in notes) for s in ("stable", "vibrato", "unstable")
    }
    return summary


def _without_reference(notes: list[Note], scale: frozenset[int] | None) -> tuple[dict, list[dict]]:
    items, cents = [], []
    for note in notes:
        item = _note_item(note, target_note(note.midi, scale))
        items.append(item)
        cents.append(item["cents"])
    summary = _base_summary(cents, [n.duration for n in notes], [n.start for n in notes], notes)
    return summary, items


# --- With a MIDI reference -----------------------------------------------------------------


def _initial_offset(contour: Contour, melody: Melody) -> tuple[int, float, float]:
    """Octave and time offset that best overlay the sung contour on the reference."""
    fps = contour.fps
    sung = contour.midi
    ref_end = int(np.ceil(melody.notes[-1].end * fps)) + 1
    ref = np.full(ref_end, np.nan)
    for n in melody.notes:
        ref[int(n.start * fps) : int(n.end * fps)] = n.midi
    ref_frames = max(1, int(np.sum(np.isfinite(ref))))

    max_delay = len(sung)
    max_lead = int(min(5.0 * fps, ref_end))
    best = (0, 0.0, -1.0)
    for octave in OCTAVES:
        r = ref + 12 * octave
        for d in range(-max_lead, max_delay, 2):
            # reference frame t is compared with recording frame t + d
            ref_start, sung_start = max(0, -d), max(0, d)
            n = min(len(r) - ref_start, len(sung) - sung_start)
            if n <= 0:
                continue
            diff = np.abs(sung[sung_start : sung_start + n] - r[ref_start : ref_start + n])
            score = float(np.sum(diff < 1.0)) / ref_frames
            if score > best[2] + 1e-9:
                best = (octave, d / fps, score)
    return best


def _align(
    notes: list[Note], ref: list[RefNote], time_scale: float, offset: float
) -> list[tuple[int | None, int | None]]:
    """Needleman-Wunsch between sung and reference notes (pitch + onset time)."""
    n, m = len(notes), len(ref)
    cost = np.zeros((n + 1, m + 1))
    cost[1:, 0] = np.arange(1, n + 1) * EXTRA_COST
    cost[0, 1:] = np.arange(1, m + 1) * MISSED_COST
    step = np.zeros((n + 1, m + 1), dtype=np.int8)  # 0 diagonal, 1 extra, 2 missed
    step[1:, 0], step[0, 1:] = 1, 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s, r = notes[i - 1], ref[j - 1]
            dt = abs(s.start - (time_scale * r.start + offset))
            match = min(abs(s.midi - r.midi), 3.0) + 0.5 * min(dt / 0.3, 4.0)
            options = (
                cost[i - 1, j - 1] + match,
                cost[i - 1, j] + EXTRA_COST,
                cost[i, j - 1] + MISSED_COST,
            )
            step[i, j] = int(np.argmin(options))
            cost[i, j] = options[step[i, j]]
    pairs: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if step[i, j] == 0:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif step[i, j] == 1:
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
    return pairs[::-1]


def _fit_timing(
    pairs, notes: list[Note], ref: list[RefNote], time_scale: float, offset: float
) -> tuple[float, float]:
    """Line sung_time = a·ref_time + b over the pairs with the right pitch."""
    good = [
        (ref[j].start, notes[i].start)
        for i, j in pairs
        if i is not None and j is not None and abs(notes[i].midi - ref[j].midi) < 1.0
    ]
    if len(good) >= 3:
        x, yv = np.array(good).T
        if np.ptp(x) > 0:
            a, b = np.polyfit(x, yv, 1)
            if 0.5 < a < 2.0:
                return float(a), float(b)
    if good:
        return time_scale, float(np.median([t_s - time_scale * t_r for t_r, t_s in good]))
    return time_scale, offset


def _with_reference(notes: list[Note], contour: Contour | None, melody: Melody):
    warnings = []
    if melody.was_polyphonic:
        warnings.append(
            q.warning(
                "polyphonic_reference", f"Track {melody.track} has chords; the top line was used."
            )
        )
    if not notes or contour is None:
        return (
            {"notes": 0, "reference_notes": len(melody.notes), "midi_track": melody.track},
            [],
            0.0,
            warnings,
        )

    octave, offset, score = _initial_offset(contour, melody)
    ref = [RefNote(n.start, n.end, n.midi + 12 * octave) for n in melody.notes]
    time_scale = 1.0
    for _ in range(2):
        pairs = _align(notes, ref, time_scale, offset)
        time_scale, offset = _fit_timing(pairs, notes, ref, time_scale, offset)

    items, cents, durations, times, sung_notes = [], [], [], [], []
    onsets = {"on_time": 0, "late": 0, "early": 0}
    missed = extra = wrong = 0
    for i, j in pairs:
        if j is None:
            extra += 1
            note = notes[i]
            items.append(
                {
                    "t": round(note.start, 2),
                    "dur": round(note.duration, 2),
                    "sung": note_name(round(note.midi)),
                    "status": "extra",
                }
            )
            continue
        r = ref[j]
        if i is None:
            missed += 1
            items.append(
                {
                    "t_ref": round(time_scale * r.start + offset, 2),
                    "expected": note_name(r.midi),
                    "status": "missed",
                }
            )
            continue
        note = notes[i]
        item = _note_item(note, r.midi, note_key="expected")
        sung = round(note.midi)
        if sung != r.midi:
            item["sung"] = note_name(sung)
        if abs(item["cents"]) > WRONG_NOTE_CENTS:
            item["wrong_note"] = True
            wrong += 1
        onset_ms = int(round(1000 * (note.start - (time_scale * r.start + offset))))
        item["onset_ms"] = onset_ms
        item["onset"] = (
            "late"
            if onset_ms > ONSET_TOLERANCE_MS
            else "early"
            if onset_ms < -ONSET_TOLERANCE_MS
            else "on_time"
        )
        onsets[item["onset"]] += 1
        items.append(item)
        cents.append(item["cents"])
        durations.append(note.duration)
        times.append(note.start)
        sung_notes.append(note)

    summary = _base_summary(cents, durations, times, sung_notes)
    summary.update(
        {
            "reference_notes": len(ref),
            "missed": missed,
            "extra_notes": extra,
            "wrong_notes": wrong,
            "onsets": onsets,
            "octave_shift": octave,
            "start_offset_ms": int(round(1000 * offset)),
            "relative_tempo": round(time_scale, 3),
            "midi_track": melody.track,
        }
    )
    if score < 0.3:
        warnings.append(
            q.warning("weak_alignment", f"Only {score:.0%} of the reference matches what was sung.")
        )
    factor = (0.5 + 0.5 * len(sung_notes) / len(ref)) * min(1.0, 0.5 + score)
    return summary, items, factor, warnings
