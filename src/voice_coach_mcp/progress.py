"""Progress log in a local markdown file (~/VoiceCoach/progress.md).

It only stores and reads entries: Claude writes the content. It exists as a tool so the log
also works in clients without file-system access (Claude Desktop).
"""

import re
from datetime import datetime
from pathlib import Path

from .config import Config
from .errors import UserError
from .output import size

HEADER = (
    "# Voice progress\n\nSession log written by voice-coach-mcp. Each session is a `## ` section.\n"
)
MAX_ENTRY = 4000


def path(config: Config) -> Path:
    return config.base_dir / "progress.md"


def _entries(text: str) -> list[str]:
    parts = re.split(r"(?m)^(?=## )", text)
    return [p.strip() for p in parts if p.startswith("## ")]


def read(config: Config, entries: int = 5) -> dict:
    file = path(config)
    if not file.exists():
        return {"file": str(file), "total_entries": 0, "entries": []}
    all_entries = _entries(file.read_text(encoding="utf-8"))
    latest = all_entries[-max(1, entries) :]
    result = {
        "file": str(file),
        "total_entries": len(all_entries),
        "entries_shown": len(latest),
        "entries": latest,
    }
    # If they do not fit, the oldest ones are dropped first.
    while len(result["entries"]) > 1 and size(result) > config.max_response_bytes:
        result["entries"] = result["entries"][1:]
        result["entries_shown"] = len(result["entries"])
    return result


def log(config: Config, entry: str) -> dict:
    text = entry.strip()
    if not text:
        raise UserError("The entry is empty.")
    if len(text) > MAX_ENTRY:
        raise UserError(f"The entry is longer than {MAX_ENTRY} characters; summarize it.")
    if not text.startswith("## "):
        text = f"## {datetime.now():%Y-%m-%d %H:%M}\n\n{text}"
    file = path(config)
    file.parent.mkdir(parents=True, exist_ok=True)
    previous = file.read_text(encoding="utf-8") if file.exists() else HEADER
    file.write_text(previous.rstrip() + "\n\n" + text + "\n", encoding="utf-8")
    return {"file": str(file), "total_entries": len(_entries(file.read_text(encoding="utf-8")))}
