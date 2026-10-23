import pytest

from voice_coach_mcp.config import cargar_config


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_COACH_DIR", str(tmp_path / "VoiceCoach"))
    return cargar_config()
