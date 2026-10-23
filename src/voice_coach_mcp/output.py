"""Builds compact JSON responses within a byte budget.

If the full result does not fit, it is saved as a JSON file next to the audio and the lists
marked as trimmable are reduced to their most relevant items.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config


@dataclass
class Trimmable:
    """A list inside the result that can be shortened, keeping its highest-priority items."""

    key: str
    priority: Callable[[dict], float] = lambda _item: 0.0


def to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def size(obj: Any) -> int:
    return len(to_json(obj).encode("utf-8"))


def details_path(audio: Path, tool: str, config: Config) -> Path:
    """`<audio>.<tool>.json` next to the audio; the analysis dir if that folder is read-only."""
    candidate = audio.with_name(f"{audio.stem}.{tool}.json")
    if _writable(candidate.parent):
        return candidate
    config.analysis_dir.mkdir(parents=True, exist_ok=True)
    return config.analysis_dir / candidate.name


def _writable(folder: Path) -> bool:
    try:
        probe = folder / ".voice-coach-probe"
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False


def _take(items: list[dict], n: int, priority: Callable[[dict], float]) -> list[dict]:
    """The n highest-priority items, in their original order."""
    if n >= len(items):
        return items
    indices = sorted(range(len(items)), key=lambda i: priority(items[i]), reverse=True)[:n]
    return [items[i] for i in sorted(indices)]


def _container(result: dict, path: str) -> tuple[dict, str]:
    """For "pauses.items" returns (copy of result["pauses"], "items"), copying along the way."""
    *parents, key = path.split(".")
    current = result
    for parent in parents:
        current[parent] = dict(current.get(parent) or {})
        current = current[parent]
    return current, key


def _trim_list(result: dict, t: Trimmable, limit: int) -> None:
    container, key = _container(result, t.key)
    items = container.get(key) or []
    low, high = 0, len(items)
    while low < high:  # largest n that fits
        mid = (low + high + 1) // 2
        container[key] = _take(items, mid, t.priority)
        container[f"{key}_shown"] = f"{mid} of {len(items)}"
        if size(result) <= limit:
            low = mid
        else:
            high = mid - 1
    container[key] = _take(items, low, t.priority)
    container[f"{key}_shown"] = f"{low} of {len(items)}"


def _trim_text(result: dict, path: str, limit: int) -> None:
    container, key = _container(result, path)
    text = container.get(key) or ""
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        container[key] = text[:mid] + "…"
        if size(result) <= limit:
            low = mid
        else:
            high = mid - 1
    container[key] = text[:low] + "…"


def fit(
    result: dict,
    *,
    audio: Path,
    tool: str,
    config: Config,
    trimmable: list[Trimmable | str] = (),
) -> str:
    """Returns the result as JSON within `config.max_response_bytes`.

    When trimming is needed, the full result is written to disk and referenced in
    `full_details`. Items are trimmed in the given order until the result fits: each
    `Trimmable` is a list (dotted paths such as "pauses.items" work) that keeps its
    highest-priority items and is marked with `<key>_shown: "n of total"`; each `str` is the
    path of a text field that gets shortened.
    """
    limit = config.max_response_bytes
    if size(result) <= limit:
        return to_json(result)

    destination = details_path(audio, tool, config)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    trimmed = dict(result)
    trimmed["full_details"] = str(destination)
    for t in trimmable:
        if size(trimmed) <= limit:
            break
        if isinstance(t, str):
            _trim_text(trimmed, t, limit)
        else:
            _trim_list(trimmed, t, limit)
    return to_json(trimmed)
