"""The voice-coach skill: valid format and consistent with the server tools."""

import re
import zipfile
from pathlib import Path

import anyio
from mcp.client import Client

from voice_coach_mcp.__main__ import package_skill
from voice_coach_mcp.server import mcp

SKILL = Path(__file__).resolve().parents[1] / "skills" / "voice-coach"


def _frontmatter() -> dict:
    text = (SKILL / "SKILL.md").read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    return dict(line.split(": ", 1) for line in m.group(1).splitlines())


def test_frontmatter():
    data = _frontmatter()
    assert data["name"] == SKILL.name == "voice-coach"
    assert re.fullmatch(r"[a-z0-9-]{1,64}", data["name"])
    assert 50 < len(data["description"]) <= 1024


def test_reference_links_exist():
    text = (SKILL / "SKILL.md").read_text()
    links = re.findall(r"\]\((references/[^)]+)\)", text)
    assert len(set(links)) == 5
    for link in links:
        assert (SKILL / link).is_file(), link


def test_mentioned_tools_exist():
    async def names():
        async with Client(mcp) as client:
            return {t.name for t in (await client.list_tools()).tools}

    tools = anyio.run(names)
    text = "\n".join(p.read_text() for p in SKILL.rglob("*.md"))
    mentioned = set(re.findall(r"`([a-z_]+)`", text)) & {
        "record_audio", "analyze_pitch", "transcribe", "speech_metrics",
        "assess_pronunciation", "read_progress", "log_progress",
    }  # fmt: skip
    assert mentioned == tools


def test_package_skill(tmp_path):
    with zipfile.ZipFile(package_skill(tmp_path / "skill.zip")) as z:
        names = set(z.namelist())
    assert "voice-coach/SKILL.md" in names
    assert "voice-coach/references/singing.md" in names
