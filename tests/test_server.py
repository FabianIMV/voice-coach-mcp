"""El servidor completo a través de un cliente MCP en memoria."""

import json

import pytest
from mcp.client import Client

from tests import falso_sounddevice
from tests import sintetico as s
from voice_coach_mcp.server import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_lista_tools_y_prompts():
    async with Client(mcp) as cliente:
        tools = {t.name for t in (await cliente.list_tools()).tools}
        prompts = {p.name for p in (await cliente.list_prompts()).prompts}
    assert {"grabar_audio", "analizar_afinacion"} <= tools
    assert prompts == {"sesion_canto", "sesion_pronunciacion", "sesion_oratoria"}


async def test_analizar_afinacion(config, tmp_path):
    ruta = s.guardar(tmp_path / "a.wav", s.secuencia([(69.2, 0.6), (71, 0.6)]))
    async with Client(mcp) as cliente:
        r = await cliente.call_tool("analizar_afinacion", {"audio": str(ruta)})
    assert not r.is_error
    datos = json.loads(r.content[0].text)
    assert [n["nota"] for n in datos["notas"]] == ["A4", "B4"]
    assert datos["notas"][0]["cents"] == pytest.approx(20, abs=3)


async def test_errores_llegan_legibles(config):
    async with Client(mcp) as cliente:
        r = await cliente.call_tool("analizar_afinacion", {"audio": "no-existe.wav"})
        r2 = await cliente.call_tool(
            "analizar_afinacion", {"audio": "no-existe.wav", "tonalidad": "X"}
        )
    assert r.is_error and "No encuentro el archivo de audio" in r.content[0].text
    assert r2.is_error


async def test_grabar_y_analizar_por_nombre(config, monkeypatch):
    falso_sounddevice.instalar(monkeypatch, samplerate=44_100)
    async with Client(mcp) as cliente:
        r = await cliente.call_tool("grabar_audio", {"segundos": 1.5, "nombre": "toma1"})
        grabacion = json.loads(r.content[0].text)
        r2 = await cliente.call_tool("analizar_afinacion", {"audio": "toma1"})
    assert grabacion["audio"].endswith("toma1.wav")
    datos = json.loads(r2.content[0].text)
    assert datos["notas"][0]["nota"] == "A4"
    assert abs(datos["notas"][0]["cents"]) <= 2


async def test_prompt_canto():
    async with Client(mcp) as cliente:
        r = await cliente.get_prompt(
            "sesion_canto", {"nivel": "principiante", "referencia_midi": "x.mid"}
        )
    texto = r.messages[0].content.text
    assert "principiante" in texto and "x.mid" in texto and "analizar_afinacion" in texto
