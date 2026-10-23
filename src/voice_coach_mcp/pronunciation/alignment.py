"""Alignment of expected vs. detected phonemes (Levenshtein with backtrace) and scores."""

from dataclasses import dataclass

from .base import PhonemeError, WordResult
from .phonemes import is_vowel, tolerated

INDEL_COST = 1.0
SUBSTITUTION_COST = 1.0
CROSS_CLASS_COST = 1.5  # vowel ↔ consonant: aligning within the class is preferred
TOLERATED_COST = 0.1  # accepted variant: not an error, but the identical phoneme wins ties
INSERTION_WEIGHT = 0.5  # in the score, an insertion weighs half a substitution or deletion


@dataclass
class Operation:
    type: str  # "ok" | "substitution" | "deletion" | "insertion"
    expected: str | None
    detected: str | None
    i: int | None  # index in expected
    j: int | None  # index in detected


def _cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if tolerated(a, b):
        return TOLERATED_COST
    return SUBSTITUTION_COST if is_vowel(a) == is_vowel(b) else CROSS_CLASS_COST


def align(expected: list[str], detected: list[str]) -> list[Operation]:
    n, m = len(expected), len(detected)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i * INDEL_COST
    for j in range(1, m + 1):
        d[0][j] = j * INDEL_COST
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(
                d[i - 1][j - 1] + _cost(expected[i - 1], detected[j - 1]),
                d[i - 1][j] + INDEL_COST,
                d[i][j - 1] + INDEL_COST,
            )
    ops: list[Operation] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + _cost(expected[i - 1], detected[j - 1]):
            a, b = expected[i - 1], detected[j - 1]
            ops.append(Operation("ok" if tolerated(a, b) else "substitution", a, b, i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + INDEL_COST:
            ops.append(Operation("deletion", expected[i - 1], None, i - 1, None))
            i -= 1
        else:
            ops.append(Operation("insertion", None, detected[j - 1], None, j - 1))
            j -= 1
    return _linking(ops[::-1])


def _linking(ops: list[Operation]) -> list[Operation]:
    """Linking r (weather‿is → ɚ ɹ ɪ) and glottal stops do not count as insertions.

    They show up because each word is phonemized separately, losing the link between words.
    """
    for k, op in enumerate(ops):
        if op.type != "insertion":
            continue
        previous = ops[k - 1].detected if k > 0 else None
        if op.detected == "ʔ" or (op.detected == "ɹ" and previous in ("ɚ", "ə")):
            op.type = "ok"
    return ops


def distance(ops: list[Operation]) -> float:
    return sum(op.type != "ok" for op in ops)


def score(n_expected: int, errors: list[PhonemeError]) -> float:
    if n_expected == 0:
        return 100.0
    penalty = sum(INSERTION_WEIGHT if e.type == "insertion" else 1.0 for e in errors)
    return max(0.0, min(100.0, 100.0 * (1 - penalty / n_expected)))


def by_word(
    words: list[str],
    expected: list[list[str]],
    ops: list[Operation],
    times: list[float] | None = None,
) -> list[WordResult]:
    """Distributes operations among words; insertions go to the preceding word."""
    word_of = [k for k, ps in enumerate(expected) for _ in ps]
    results = [
        WordResult(word=w, score=100.0, expected=list(e))
        for w, e in zip(words, expected, strict=True)
    ]
    current = 0
    for op in ops:
        if op.i is not None:
            current = word_of[op.i]
        r = results[current] if results else None
        if r is None:
            continue
        if op.detected is not None:
            r.detected.append(op.detected)
            if times is not None and r.start is None and op.j is not None:
                r.start = times[op.j]
        if op.type != "ok":
            r.errors.append(PhonemeError(op.type, op.expected, op.detected))
    for r in results:
        r.score = score(len(r.expected), r.errors)
        r.missing = bool(r.expected) and not r.detected
    return results


def overall_score(results: list[WordResult]) -> float:
    total = sum(len(r.expected) for r in results)
    errors = [e for r in results for e in r.errors]
    return score(total, errors)
