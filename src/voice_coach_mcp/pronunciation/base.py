"""Common interface of the pronunciation backends and their normalized result."""

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..config import Config


@dataclass
class PhonemeError:
    type: str  # "substitution" | "deletion" | "insertion"
    expected: str | None = None
    detected: str | None = None

    def to_dict(self) -> dict:
        d = {"type": self.type}
        if self.expected:
            d["expected"] = self.expected
        if self.detected:
            d["detected"] = self.detected
        return d


@dataclass
class WordResult:
    word: str
    score: float  # 0–100
    expected: list[str] = field(default_factory=list)
    detected: list[str] = field(default_factory=list)
    errors: list[PhonemeError] = field(default_factory=list)
    start: float | None = None
    missing: bool = False  # the whole word was not said


@dataclass
class PronunciationResult:
    backend: str
    words: list[WordResult]
    overall_score: float
    model_confidence: float  # 0–1, how sure the backend is about what it detected
    relative_distance: float  # edit distance / expected phonemes
    expected_phonemes: list[str] = field(default_factory=list)
    detected_phonemes: list[str] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)  # backend-specific metrics


class PronunciationBackend(Protocol):
    name: str

    def assess(
        self, y: np.ndarray, text: str, language: str, config: Config
    ) -> PronunciationResult: ...
