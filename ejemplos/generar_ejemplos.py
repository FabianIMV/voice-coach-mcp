"""Regenera los audios sintéticos de ejemplo y las salidas reales de cada tool.

Las tools de análisis se llaman a través del servidor real por stdio (como lo haría Claude).
`grabar_audio` necesita un micrófono: aquí se ejecuta en proceso con un dispositivo simulado.
La voz de los ejemplos de habla se sintetiza con espeak-ng y la de pronunciación con Piper (voz
LJSpeech, de dominio público; se ejecuta con uvx). Requiere `espeak-ng` y los extras `habla` y
`pronunciacion`.

Uso: uv run python ejemplos/generar_ejemplos.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import anyio
import numpy as np
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tests import falso_sounddevice, tts  # noqa: E402
from tests import sintetico as s  # noqa: E402

AUDIO = RAIZ / "ejemplos" / "audio"
SALIDAS = RAIZ / "ejemplos" / "salidas"

DISCURSO_ES = (
    'Bueno, eh, hoy quiero hablarles de un tema importante. <break time="1200ms"/> '
    "O sea, la forma en que comunicamos nuestras ideas cambia todo. Este, cuando hablamos en "
    'público, mmm, muchas veces nos ponemos nerviosos. <break time="900ms"/> Entonces, la '
    "clave está en practicar, ¿no? Y practicar con datos concretos."
)
DISCURSO_EN = (
    'Um, so today I want to talk about, uh, public speaking. <break time="1000ms"/> You know, '
    "most people feel nervous, like, before a big talk. I mean, that is completely normal. "
    '<break time="800ms"/> The key is to practice with real feedback.'
)

FRASE = "I think the very best things in life are free."
FRASE_CON_ERRORES = (
    "I sink the berry best sings in life are free."  # θ→s y v→b, típicos de hispanohablantes
)

ENTRADA_PROGRESO = """## 2026-10-23 · Canto · Escala de Do mayor (intermedio)

- **Objetivo**: afinar la parte aguda de la escala.
- **Tomas**: 3 (`escala-do-toma1` … `toma3`)
- **Métricas**: dentro de ±25 cents 62 % → 75 %; B4 −58 → −42 cents; E4 −30 cents sin cambio.
- **Lo que mejoró**: la C5 final quedó centrada (−2 cents) con vibrato regular de 5,5 Hz.
- **Foco siguiente**: B4 y E4 a menos de ±20 cents con notas tenidas en *ng*."""

# Melodía original de 8 compases simples (sin derechos), 0,5 s por negra.
MELODIA = [
    (67, 1),
    (69, 1),
    (71, 2),
    (69, 1),
    (67, 1),
    (64, 2),
    (62, 1),
    (64, 1),
    (67, 1),
    (69, 1),
    (67, 4),
]


def _o_existente(ruta: Path, texto: str) -> Path:
    return ruta if ruta.exists() else tts.sintetizar_piper(texto, ruta)


def preparar_audios() -> dict[str, Path]:
    AUDIO.mkdir(parents=True, exist_ok=True)
    rutas = {}

    # 1) Escala de Do mayor con desafinaciones conocidas (cents) y una nota con vibrato.
    desv = [0, -8, -30, 5, 22, -15, -42, 3]
    escala = [60, 62, 64, 65, 67, 69, 71, 72]
    partes = [s.silencio(0.4)]
    for i, (m, d) in enumerate(zip(escala, desv, strict=True)):
        vib = 45 if i == 7 else 0
        partes += [s.tono(m + d / 100, 1.4 if i == 7 else 0.6, vibrato_cents=vib), s.silencio(0.12)]
    partes.append(s.silencio(0.4))
    rutas["escala"] = s.guardar(
        AUDIO / "escala_do_mayor.wav", s.con_ruido(np.concatenate(partes), 35)
    )

    # 2) Referencia MIDI y una versión "cantada" una octava abajo, que entra 1 s tarde,
    #    con una nota calante, una entrada tardía, una nota inestable y vibrato en la final.
    t, ref = 0.0, []
    for m, negras in MELODIA:
        ref.append((m, t, t + negras * 0.5 - 0.05))
        t += negras * 0.5
    rutas["midi"] = s.midi_melodia(AUDIO / "melodia_referencia.mid", ref)

    partes, cursor, inicio = [s.silencio(1.0)], 1.0, 1.0
    for i, (m, ini, fin) in enumerate(ref):
        retraso = 0.14 if i == 5 else 0.0
        comienzo = inicio + ini + retraso
        partes.append(s.silencio(comienzo - cursor))
        altura = m - 12 + (-0.33 if i == 2 else 0.0) + (0.18 if i == 8 else 0.0)
        tono = s.tono(
            altura,
            fin - ini - retraso,
            vibrato_cents=40 if i == len(ref) - 1 else 0,
            jitter_cents=30 if i == 6 else 0,
            semilla=i,
        )
        partes.append(tono)
        cursor = comienzo + len(tono) / s.SR
    partes.append(s.silencio(0.6))
    rutas["cantada"] = s.guardar(
        AUDIO / "melodia_cantada.wav", s.con_ruido(np.concatenate(partes), 35)
    )
    rutas["discurso_es"] = tts.sintetizar(DISCURSO_ES, "es", AUDIO / "discurso_es.wav")
    rutas["discurso_en"] = tts.sintetizar(DISCURSO_EN, "en", AUDIO / "discurso_en.wav", 160)
    # Piper no es determinista: se reutilizan los audios existentes para que los ejemplos no cambien.
    rutas["pron_correcta"] = _o_existente(AUDIO / "pronunciacion_correcta.wav", FRASE)
    rutas["pron_errores"] = _o_existente(AUDIO / "pronunciacion_errores.wav", FRASE_CON_ERRORES)
    return rutas


def _limpiar(texto: str, temporal: str) -> dict:
    """Rutas absolutas → relativas al repo para que el ejemplo sea legible."""
    texto = texto.replace(str(RAIZ) + "/", "").replace(temporal, "~/VoiceCoach")
    return json.loads(texto)


async def llamar_por_stdio(rutas: dict[str, Path], temporal: str) -> dict[str, dict]:
    servidor = StdioServerParameters(
        command=sys.executable,
        args=["-m", "voice_coach_mcp"],
        env={**os.environ, "VOICE_COACH_DIR": temporal},
        cwd=str(RAIZ),
    )
    llamadas = [
        ("analizar_afinacion_temperado", "analizar_afinacion", {"audio": str(rutas["escala"])}),
        (
            "analizar_afinacion_tonalidad",
            "analizar_afinacion",
            {"audio": str(rutas["escala"]), "tonalidad": "Sol mayor"},
        ),
        (
            "analizar_afinacion_referencia_midi",
            "analizar_afinacion",
            {"audio": str(rutas["cantada"]), "referencia_midi": str(rutas["midi"])},
        ),
        ("transcribir_en", "transcribir", {"audio": str(rutas["discurso_en"])}),
        (
            "metricas_discurso_es",
            "metricas_discurso",
            {"audio": str(rutas["discurso_es"]), "idioma": "es"},
        ),
        (
            "evaluar_pronunciacion_correcta",
            "evaluar_pronunciacion",
            {"audio": str(rutas["pron_correcta"]), "texto_esperado": FRASE},
        ),
        (
            "evaluar_pronunciacion_con_errores",
            "evaluar_pronunciacion",
            {"audio": str(rutas["pron_errores"]), "texto_esperado": FRASE},
        ),
        (
            "metricas_discurso_en",
            "metricas_discurso",
            {"audio": str(rutas["discurso_en"]), "idioma": "en"},
        ),
        ("registrar_progreso", "registrar_progreso", {"entrada": ENTRADA_PROGRESO}),
        ("leer_progreso", "leer_progreso", {"entradas": 3}),
    ]
    salidas = {}
    async with Client(servidor, read_timeout_seconds=600) as cliente:
        for nombre, tool, args in llamadas:
            r = await cliente.call_tool(tool, args)
            texto = r.content[0].text
            print(f"{nombre}: {len(texto.encode())} bytes", file=sys.stderr)
            salidas[nombre] = {
                "llamada": {"tool": tool, "argumentos": args},
                "respuesta": _limpiar(texto, temporal),
            }
    return salidas


async def grabar_simulado(temporal: str) -> dict[str, dict]:
    import pytest

    from voice_coach_mcp.server import mcp

    salidas = {}
    for modo, nombre in (
        ("tono", "grabar_audio_simulado"),
        ("silencio", "grabar_audio_sin_permiso"),
    ):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("VOICE_COACH_DIR", temporal)
            falso_sounddevice.instalar(mp, modo=modo)
            async with Client(mcp) as cliente:
                args = {"segundos": 3, "nombre": "toma"}
                r = await cliente.call_tool("grabar_audio", args)
        salidas[nombre] = {
            "nota": "Dispositivo de entrada simulado (este entorno no tiene micrófono).",
            "llamada": {"tool": "grabar_audio", "argumentos": args},
            "respuesta": _limpiar(r.content[0].text, temporal),
        }
    return salidas


async def main() -> None:
    rutas = preparar_audios()
    rutas = {k: v.relative_to(RAIZ) for k, v in rutas.items()}
    SALIDAS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporal:
        salidas = await llamar_por_stdio(rutas, temporal)
        salidas |= await grabar_simulado(temporal)
    for nombre, contenido in salidas.items():
        (SALIDAS / f"{nombre}.json").write_text(
            json.dumps(contenido, ensure_ascii=False, indent=2) + "\n"
        )


if __name__ == "__main__":
    anyio.run(main)
