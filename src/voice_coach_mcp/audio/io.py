"""Audio loading and saving, normalized to 16 kHz mono float32."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from ..config import SAMPLE_RATE, Config
from ..errors import UserError


def resolve_path(audio: str, config: Config) -> Path:
    """Accepts absolute or relative paths, or the name of a recording in the recordings dir."""
    path = Path(audio).expanduser()
    if path.is_file():
        return path.resolve()
    for candidate in (config.recordings_dir / audio, config.recordings_dir / f"{audio}.wav"):
        if candidate.is_file():
            return candidate.resolve()
    raise UserError(f"Audio file not found: {audio}")


def load(path: Path, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Reads wav/flac/ogg/mp3 with libsndfile; other formats (m4a, aac…) through ffmpeg."""
    try:
        y, original_sr = sf.read(path, dtype="float32", always_2d=True)
        y = y.mean(axis=1)
    except sf.LibsndfileError:
        return _load_ffmpeg(path, sr)
    if original_sr != sr:
        import librosa

        y = librosa.resample(y, orig_sr=original_sr, target_sr=sr)
    return np.ascontiguousarray(y, dtype=np.float32)


def _load_ffmpeg(path: Path, sr: int) -> np.ndarray:
    if shutil.which("ffmpeg") is None:
        raise UserError(
            f"Cannot read {path.name}: unsupported format without ffmpeg (brew install ffmpeg)."
        )
    process = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(sr),
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise UserError(f"ffmpeg could not read {path.name}: {process.stderr.decode()[:200]}")
    return np.frombuffer(process.stdout, dtype=np.float32).copy()


def save_wav(path: Path, y: np.ndarray, sr: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.clip(y, -1.0, 1.0), sr, subtype="PCM_16")
