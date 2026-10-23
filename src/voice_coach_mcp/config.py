"""Settings read from environment variables on every call (so tests can change them)."""

import os
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class Config:
    base_dir: Path
    max_recording_seconds: float
    a4_hz: float
    max_response_bytes: int
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    pronunciation_backend: str
    fillers_file: Path | None

    @property
    def recordings_dir(self) -> Path:
        return self.base_dir / "recordings"

    @property
    def analysis_dir(self) -> Path:
        return self.base_dir / "analysis"


def _float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


def load_config() -> Config:
    fillers = os.environ.get("VOICE_COACH_FILLERS")
    return Config(
        base_dir=Path(os.environ.get("VOICE_COACH_DIR", "~/VoiceCoach")).expanduser(),
        max_recording_seconds=_float("VOICE_COACH_MAX_SECONDS", 120.0),
        a4_hz=_float("VOICE_COACH_A4_HZ", 440.0),
        max_response_bytes=int(_float("VOICE_COACH_MAX_BYTES", 2048)),
        whisper_model=os.environ.get("VOICE_COACH_WHISPER_MODEL", "small"),
        whisper_device=os.environ.get("VOICE_COACH_WHISPER_DEVICE", "cpu"),
        whisper_compute_type=os.environ.get("VOICE_COACH_WHISPER_COMPUTE_TYPE", "int8"),
        pronunciation_backend=os.environ.get("VOICE_COACH_PRONUNCIATION_BACKEND", "local"),
        fillers_file=Path(fillers).expanduser() if fillers else None,
    )
