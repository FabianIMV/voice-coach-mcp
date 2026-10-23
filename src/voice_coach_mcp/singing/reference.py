"""Reference melody from a MIDI file provided by the user."""

from dataclasses import dataclass
from pathlib import Path

from ..errors import UserError


@dataclass
class RefNote:
    start: float
    end: float
    midi: int


@dataclass
class Melody:
    notes: list[RefNote]
    track: str
    was_polyphonic: bool


def load_melody(path: Path, track: int | None = None) -> Melody:
    """Uses the given track or, by default, the non-drum track with the most notes.

    If the track has overlapping notes, the top line is kept (skyline).
    """
    import pretty_midi

    try:
        midi = pretty_midi.PrettyMIDI(str(path))
    except Exception as e:  # pretty_midi/mido raise several error types
        raise UserError(f"Could not read the MIDI file {path.name}: {e}") from e

    candidates = [
        (i, inst) for i, inst in enumerate(midi.instruments) if not inst.is_drum and inst.notes
    ]
    if not candidates:
        raise UserError(f"The MIDI file {path.name} has no melodic tracks with notes.")
    if track is not None:
        chosen = [c for c in candidates if c[0] == track]
        if not chosen:
            available = ", ".join(f"{i} ({inst.name or 'unnamed'})" for i, inst in candidates)
            raise UserError(f"Track {track} does not exist or has no notes. Available: {available}")
        index, instrument = chosen[0]
    else:
        index, instrument = max(candidates, key=lambda c: len(c[1].notes))

    notes = sorted(instrument.notes, key=lambda n: (n.start, -n.pitch))
    melody: list[RefNote] = []
    polyphonic = False
    for n in notes:
        if melody and n.start < melody[-1].end - 1e-3:
            polyphonic = True
            if n.pitch <= melody[-1].midi:
                continue  # below the sounding note: not the melody
            melody[-1].end = n.start
            if melody[-1].end - melody[-1].start < 1e-3:
                melody.pop()
        melody.append(RefNote(start=float(n.start), end=float(n.end), midi=int(n.pitch)))
    name = instrument.name.strip() or f"track {index}"
    return Melody(notes=melody, track=f"{index}: {name}", was_polyphonic=polyphonic)
