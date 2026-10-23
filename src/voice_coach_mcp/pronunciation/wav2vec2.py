"""Local backend: wav2vec2 phoneme model (CTC) + alignment with the expected phonemes."""

import os
import threading

import numpy as np

from ..audio import quality as q
from ..config import SAMPLE_RATE, Config
from ..errors import UserError
from . import alignment, phonemes
from .base import PronunciationResult

MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"
SECONDS_PER_FRAME = 0.02
MAX_SECONDS = 60.0

_cache: dict[str, tuple] = {}
_lock = threading.Lock()


def _device() -> str:
    import torch

    requested = os.environ.get("VOICE_COACH_PRONUNCIATION_DEVICE", "auto")
    if requested != "auto":
        return requested
    return "mps" if torch.backends.mps.is_available() else "cpu"


def cache_first(load, *args, **kwargs):
    """Local cache only first (no network, works offline); download if missing."""
    try:
        return load(*args, local_files_only=True, **kwargs)
    except OSError:
        return load(*args, **kwargs)


def load_model():
    with _lock:
        if "model" not in _cache:
            try:
                from transformers import AutoModelForCTC, AutoProcessor
            except ImportError as e:
                raise UserError(
                    "torch/transformers are missing. Install them with: uv sync --extra pronunciation"
                ) from e
            # The model repo only has pytorch_model.bin on main: without this, transformers
            # also downloads a safetensors copy (1.26 GB) from a PR of the repo.
            os.environ.setdefault("DISABLE_SAFETENSORS_CONVERSION", "1")
            device = _device()
            processor = cache_first(AutoProcessor.from_pretrained, MODEL)
            model = cache_first(AutoModelForCTC.from_pretrained, MODEL)
            _cache["model"] = (processor, model.eval().to(device), device)
        return _cache["model"]


def recognize(y: np.ndarray) -> tuple[list[str], list[float], list[float]]:
    """Greedy CTC decoding: phonemes, start time and mean probability of each one."""
    import torch

    processor, model, device = load_model()
    inputs = processor(y, sampling_rate=SAMPLE_RATE, return_tensors="pt").input_values.to(device)
    with _lock, torch.no_grad():
        prob = model(inputs).logits[0].float().softmax(-1).cpu().numpy()
    ids = prob.argmax(-1)
    tokenizer = processor.tokenizer
    blank = tokenizer.pad_token_id
    phones, times, confidences = [], [], []
    start = 0
    for t in range(1, len(ids) + 1):
        if t < len(ids) and ids[t] == ids[start]:
            continue
        if ids[start] != blank:
            phones.append(tokenizer.convert_ids_to_tokens(int(ids[start])))
            times.append(round(start * SECONDS_PER_FRAME, 2))
            confidences.append(float(prob[start:t, ids[start]].mean()))
        start = t
    return phones, times, confidences


class Wav2Vec2Backend:
    name = "wav2vec2-local"

    def assess(
        self, y: np.ndarray, text: str, language: str, config: Config
    ) -> PronunciationResult:
        if len(y) / SAMPLE_RATE > MAX_SECONDS:
            raise UserError(
                f"The audio is longer than {MAX_SECONDS:.0f} s; record shorter phrases."
            )
        words = phonemes.words_of(text)
        if not words:
            raise UserError("expected_text has no words.")
        expected = phonemes.expected_by_word(words, language)
        raw, raw_times, confidences = recognize(y)

        # Normalization can split a token in two; each part inherits its time and confidence.
        detected, times = [], []
        for p, t in zip(raw, raw_times, strict=True):
            parts = phonemes.normalize([p])
            detected += parts
            times += [t] * len(parts)

        flat = [p for ps in expected for p in ps]
        ops = alignment.align(flat, detected)
        results = alignment.by_word(words, expected, ops, times)
        distance = alignment.distance(ops) / max(1, len(flat))
        warnings = []
        if distance > 0.6:
            warnings.append(
                q.warning(
                    "text_mismatch",
                    f"What was detected differs from the expected text in {distance:.0%} of the phonemes: was a different text read?",
                )
            )
        return PronunciationResult(
            backend=self.name,
            words=results,
            overall_score=alignment.overall_score(results),
            model_confidence=float(np.mean(confidences)) if confidences else 0.0,
            relative_distance=distance,
            expected_phonemes=flat,
            detected_phonemes=detected,
            warnings=warnings,
        )
