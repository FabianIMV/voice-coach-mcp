"""Optional backend: Azure Pronunciation Assessment (requires an Azure Speech key and region).

Enabled with VOICE_COACH_PRONUNCIATION_BACKEND=azure, AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.
The audio is sent to Azure; the local backend sends nothing off the machine.
"""

import json
import os
import tempfile
from pathlib import Path

import numpy as np

from ..audio import quality as q
from ..audio.io import save_wav
from ..config import SAMPLE_RATE, Config
from ..errors import UserError
from .base import PhonemeError, PronunciationResult, WordResult

PHONEME_THRESHOLD = 60  # phoneme AccuracyScore below which it is reported as an error
MAX_SECONDS = 30.0  # recognize_once assesses a single utterance
TICKS_PER_SECOND = 10_000_000


def parse(response: dict) -> PronunciationResult:
    """Converts Azure's JSON (SpeechServiceResponse_JsonResult) into the common schema."""
    if response.get("RecognitionStatus") != "Success" or not response.get("NBest"):
        raise UserError(
            f"Azure did not recognize speech (status: {response.get('RecognitionStatus')})."
        )
    best = response["NBest"][0]
    assessment = best.get("PronunciationAssessment", {})
    words: list[WordResult] = []
    for w in best.get("Words", []):
        pa = w.get("PronunciationAssessment", {})
        error_type = pa.get("ErrorType", "None")
        start = round(w["Offset"] / TICKS_PER_SECOND, 2) if "Offset" in w else None
        if error_type == "Insertion":
            if words:
                words[-1].errors.append(PhonemeError("insertion", detected=w["Word"]))
            continue
        expected, detected, errors = [], [], []
        for p in w.get("Phonemes", []):
            phoneme = p["Phoneme"]
            expected.append(phoneme)
            ppa = p.get("PronunciationAssessment", {})
            nbest = ppa.get("NBestPhonemes") or []
            alternative = nbest[0]["Phoneme"] if nbest else phoneme
            detected.append(alternative)
            if ppa.get("AccuracyScore", 100) < PHONEME_THRESHOLD:
                errors.append(
                    PhonemeError(
                        "substitution", phoneme, alternative if alternative != phoneme else None
                    )
                )
        missing = error_type == "Omission"
        if missing:
            errors = [PhonemeError("deletion", p) for p in expected] or [PhonemeError("deletion")]
            detected = []
        words.append(
            WordResult(
                word=w["Word"],
                score=0.0 if missing else float(pa.get("AccuracyScore", 0)),
                expected=expected,
                detected=detected,
                errors=errors,
                start=None if missing else start,
                missing=missing,
            )
        )
    completeness = float(assessment.get("CompletenessScore", 100))
    warnings = []
    if completeness < 40:
        warnings.append(
            q.warning("text_mismatch", f"Azure reports completeness {completeness:.0f}/100.")
        )
    return PronunciationResult(
        backend="azure",
        words=words,
        overall_score=float(assessment.get("AccuracyScore", 0)),
        model_confidence=float(best.get("Confidence", 0)),
        relative_distance=1 - completeness / 100,
        expected_phonemes=[p for w in words for p in w.expected],
        detected_phonemes=[p for w in words for p in w.detected],
        warnings=warnings,
        extra={
            k: assessment[c]
            for k, c in (
                ("fluency", "FluencyScore"),
                ("completeness", "CompletenessScore"),
                ("prosody", "ProsodyScore"),
            )
            if c in assessment
        },
    )


class AzureBackend:
    name = "azure"

    def assess(
        self, y: np.ndarray, text: str, language: str, config: Config
    ) -> PronunciationResult:
        key, region = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
        if not key or not region:
            raise UserError("The azure backend requires AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.")
        if len(y) / SAMPLE_RATE > MAX_SECONDS:
            raise UserError(
                f"With Azure, each assessment accepts up to {MAX_SECONDS:.0f} s of audio."
            )
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as e:
            raise UserError(
                "The Azure SDK is missing. Install it with: uv sync --extra azure"
            ) from e

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audio.wav"
            save_wav(path, y)
            speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
            speech_config.speech_recognition_language = language
            assessment = speechsdk.PronunciationAssessmentConfig(
                reference_text=text,
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                enable_miscue=True,
            )
            assessment.phoneme_alphabet = "IPA"
            assessment.nbest_phoneme_count = 1
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=speechsdk.audio.AudioConfig(filename=str(path)),
            )
            assessment.apply_to(recognizer)
            result = recognizer.recognize_once()
        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            raise UserError(
                f"Azure canceled the assessment: {details.reason} {details.error_details}"
            )
        raw = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
        return parse(json.loads(raw))
