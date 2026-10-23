"""La skill coach-de-voz: formato válido y coherente con las tools del servidor."""

import re
import zipfile
from pathlib import Path

import anyio
import pytest
from mcp.client import Client

from voice_coach_mcp.__main__ import empaquetar_skill
from voice_coach_mcp.server import mcp

SKILL = Path(__file__).resolve().parents[1] / "skills" / "coach-de-voz"


def _frontmatter() -> dict:
    texto = (SKILL / "SKILL.md").read_text()
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.DOTALL)
    assert m, "SKILL.md debe empezar con frontmatter YAML"
    return dict(linea.split(": ", 1) for linea in m.group(1).splitlines())


def test_frontmatter():
    datos = _frontmatter()
    assert datos["name"] == SKILL.name == "coach-de-voz"
    assert re.fullmatch(r"[a-z0-9-]{1,64}", datos["name"])
    assert 50 < len(datos["description"]) <= 1024


def test_enlaces_a_referencias_existen():
    texto = (SKILL / "SKILL.md").read_text()
    enlaces = re.findall(r"\]\((references/[^)]+)\)", texto)
    assert len(set(enlaces)) == 5
    for enlace in enlaces:
        assert (SKILL / enlace).is_file(), enlace


def test_tools_mencionadas_existen():
    async def nombres():
        async with Client(mcp) as cliente:
            return {t.name for t in (await cliente.list_tools()).tools}

    tools = anyio.run(nombres)
    texto = "\n".join(p.read_text() for p in SKILL.rglob("*.md"))
    mencionadas = set(re.findall(r"`([a-z_]+)`", texto)) & {
        "grabar_audio", "analizar_afinacion", "transcribir", "metricas_discurso",
        "evaluar_pronunciacion", "leer_progreso", "registrar_progreso",
    }  # fmt: skip
    assert mencionadas == tools


def test_empaquetar(tmp_path):
    destino = empaquetar_skill(tmp_path / "skill.zip")
    with zipfile.ZipFile(destino) as z:
        nombres = set(z.namelist())
    assert "coach-de-voz/SKILL.md" in nombres
    assert "coach-de-voz/references/canto.md" in nombres


@pytest.mark.parametrize("archivo", sorted(p.name for p in (SKILL / "references").glob("*.md")))
def test_referencias_sin_voseo(archivo):
    texto = (SKILL / "references" / archivo).read_text().lower()
    for palabra in ("tenés", "fijate", "mirá", "podés", "querés"):
        assert palabra not in texto
