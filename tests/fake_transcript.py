"""Hand-built transcripts to test metrics without loading Whisper."""

from voice_coach_mcp.speech.transcription import Segment, Transcript, Word


def build(sentences: list[list[tuple[str, float, float]]], language: str = "en") -> Transcript:
    """sentences = [[(text, start, end), ...], ...]; each sentence is a segment."""
    segments = []
    for sentence in sentences:
        words = [Word(t, s, e, 0.95) for t, s, e in sentence]
        segments.append(
            Segment(sentence[0][1], sentence[-1][2], " ".join(t for t, _, _ in sentence), words)
        )
    return Transcript(language=language, language_prob=0.99, segments=segments)


def regular(
    text: str, start: float = 0.0, dur: float = 0.3, gap: float = 0.1
) -> list[tuple[str, float, float]]:
    """A sentence whose words have a fixed duration and are separated by fixed gaps."""
    sentence, t = [], start
    for word in text.split():
        sentence.append((word, round(t, 3), round(t + dur, 3)))
        t += dur + gap
    return sentence
