"""El servidor completo a través de un cliente MCP en memoria."""

import json

import pytest
from mcp.client import Client

from tests import falsa_transcripcion as ft
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
    assert tools == {
        "grabar_audio",
        "analizar_afinacion",
        "transcribir",
        "metricas_discurso",
        "evaluar_pronunciacion",
    }
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


async def test_metricas_discurso_con_transcripcion_simulada(config, tmp_path, monkeypatch):
    frases = [
        ft.regular("Bueno, eh, hoy hablamos de voz."),
        ft.regular("O sea, practicar sirve.", inicio=3.5),
    ]
    monkeypatch.setattr(
        "voice_coach_mcp.habla.discurso.transcribir", lambda *a, **k: ft.armar(frases)
    )
    y = s.secuencia([(48, 2.5), (50, 1.6)], pausa=1.0)
    ruta = s.guardar(tmp_path / "habla.wav", y)
    async with Client(mcp) as cliente:
        r = await cliente.call_tool("metricas_discurso", {"audio": str(ruta), "idioma": "es-CL"})
    datos = json.loads(r.content[0].text)
    assert datos["idioma"] == "es"
    assert datos["muletillas"]["por_tipo"] == {"bueno": 1, "eh": 1, "o sea": 1}
    assert datos["pausas"]["cantidad"] == 1
    assert datos["segmentos"][1]["texto"].startswith("O sea")


async def test_transcribir_sin_habla(config, tmp_path):
    ruta = s.guardar(tmp_path / "mudo.wav", s.silencio(2.0))
    async with Client(mcp) as cliente:
        r = await cliente.call_tool("transcribir", {"audio": str(ruta)})
    datos = json.loads(r.content[0].text)
    assert datos["confianza"]["valor"] == 0
    assert "silencio_digital" in {a["codigo"] for a in datos["advertencias"]}


async def test_falta_extra_habla_da_instruccion(config, tmp_path, monkeypatch):
    import sys

    from voice_coach_mcp.habla import transcripcion

    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # simula que no está instalado
    monkeypatch.setattr(transcripcion, "_modelos", {})
    ruta = s.guardar(tmp_path / "a.wav", s.secuencia([(60, 1.0)]))
    async with Client(mcp) as cliente:
        r = await cliente.call_tool("transcribir", {"audio": str(ruta)})
    assert r.is_error and "uv sync --extra habla" in r.content[0].text


class _BackendFalso:
    """Simula lo que detectaría el modelo: "very" con b y "things" con s."""

    nombre = "falso"

    def evaluar(self, y, texto, idioma, config):
        from voice_coach_mcp.pronunciacion import alineacion
        from voice_coach_mcp.pronunciacion.base import ResultadoPronunciacion

        palabras = ["The", "very", "best", "things"]
        esperados = [["ð", "ə"], ["v", "ɛ", "ɹ", "i"], ["b", "ɛ", "s", "t"], ["θ", "ɪ", "ŋ", "z"]]
        detectados = ["ð", "ə", "b", "ɛ", "ɹ", "i", "b", "ɛ", "s", "t", "s", "ɪ", "ŋ", "z"]
        plano = [f for fs in esperados for f in fs]
        ops = alineacion.alinear(plano, detectados)
        r = alineacion.por_palabra(
            palabras, esperados, ops, [i * 0.1 for i in range(len(detectados))]
        )
        return ResultadoPronunciacion(
            "falso", r, alineacion.puntaje_global(r), 0.9, 2 / 14, plano, detectados
        )


async def test_evaluar_pronunciacion_con_backend_simulado(config, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "voice_coach_mcp.pronunciacion.evaluacion.backend", lambda c: _BackendFalso()
    )
    ruta = s.guardar(tmp_path / "frase.wav", s.secuencia([(55, 1.5)]))
    async with Client(mcp) as cliente:
        r = await cliente.call_tool(
            "evaluar_pronunciacion", {"audio": str(ruta), "texto_esperado": "The very best things"}
        )
    datos = json.loads(r.content[0].text)
    res = datos["resumen"]
    assert res["puntaje_global"] == round(100 * (1 - 2 / 14))
    assert res["palabras_con_errores"] == 2
    assert res["errores"] == {"sustitucion": 2, "omision": 0, "insercion": 0}
    assert {"esperado": "θ", "detectado": "s", "veces": 1} in res["confusiones_frecuentes"]
    very = datos["palabras"][1]
    assert very == {
        "palabra": "very",
        "puntaje": 75,
        "t": 0.2,
        "esperado": "v ɛ ɹ i",
        "detectado": "b ɛ ɹ i",
        "errores": [{"tipo": "sustitucion", "esperado": "v", "detectado": "b"}],
    }
    assert datos["palabras"][0] == {"palabra": "The", "puntaje": 100, "t": 0.0}


async def test_backend_desconocido(config, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_COACH_PRONUNCIACION_BACKEND", "otro")
    ruta = s.guardar(tmp_path / "frase.wav", s.secuencia([(55, 1.0)]))
    async with Client(mcp) as cliente:
        r = await cliente.call_tool(
            "evaluar_pronunciacion", {"audio": str(ruta), "texto_esperado": "hi"}
        )
    assert r.is_error and "local" in r.content[0].text
