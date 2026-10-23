"""Servidor MCP (stdio): registro de tools y prompts. La lógica vive en los subpaquetes."""

import functools
import logging
import time

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__, prompts
from .audio.grabacion import grabar
from .canto.afinacion import analizar
from .config import cargar_config
from .errores import ErrorUsuario
from .habla.discurso import analizar_discurso, analizar_transcripcion
from .salida import a_json

log = logging.getLogger("voice_coach_mcp")

INSTRUCCIONES = """Este servidor mide audio para que actúes como coach de voz (canto, pronunciación en
inglés y oratoria). Las tools devuelven mediciones en JSON compacto con `confianza` y `advertencias`;
la interpretación y el feedback los das tú. Si una respuesta trae `detalle_completo`, ahí hay un
JSON con todo el detalle. Los audios se pueden pasar por ruta o por el nombre devuelto por grabar_audio."""

mcp = MCPServer("voice-coach", instructions=INSTRUCCIONES, version=__version__)


def _errores_legibles(fn):
    """Convierte ErrorUsuario en ToolError para que el mensaje llegue tal cual a Claude."""

    @functools.wraps(fn)
    async def envoltura(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ErrorUsuario as e:
            raise ToolError(str(e)) from e

    return envoltura


@mcp.tool()
@_errores_legibles
async def grabar_audio(segundos: float, ctx: Context, nombre: str | None = None) -> str:
    """Graba del micrófono del equipo y guarda un .wav 16 kHz mono.

    Args:
        segundos: duración de la grabación (máx. 120 por defecto). Avisa al usuario antes de llamar.
        nombre: nombre opcional del archivo (sin extensión); por defecto, fecha y hora.

    Devuelve `audio` (ruta del .wav), niveles (pico/RMS en dBFS, SNR estimado, % de clipping),
    `confianza` y `advertencias`. La advertencia `sin_permiso_microfono` indica que macOS no
    entregó audio: el usuario debe habilitar el micrófono para la app en Ajustes del Sistema.
    """
    config = cargar_config()
    resultado: dict = {}

    async def grabar_en_hilo():
        resultado.update(await anyio.to_thread.run_sync(grabar, segundos, nombre, config))

    inicio = time.monotonic()
    async with anyio.create_task_group() as tg:
        tg.start_soon(grabar_en_hilo)
        while not resultado:
            transcurrido = min(time.monotonic() - inicio, segundos)
            try:
                await ctx.report_progress(transcurrido, segundos, "grabando")
            except Exception:  # el cliente puede no pedir progreso
                log.debug("no se pudo reportar progreso", exc_info=True)
            await anyio.sleep(1.0)
    return a_json(resultado)


@mcp.tool()
@_errores_legibles
async def analizar_afinacion(
    audio: str,
    referencia_midi: str | None = None,
    tonalidad: str | None = None,
    pista_midi: int | None = None,
) -> str:
    """Mide la afinación de un audio cantado (voz sola, una línea melódica).

    Args:
        audio: ruta del audio (wav/flac/mp3/m4a) o nombre devuelto por grabar_audio.
        referencia_midi: ruta opcional a un .mid con la melodía esperada. Tolera que se cante una
            octava arriba/abajo, que se empiece en otro momento y un tempo algo distinto.
        tonalidad: opcional sin MIDI, p. ej. "A minor", "La menor", "Sol mayor": cada nota se compara
            con la nota más cercana de esa escala. Sin ella, con la nota temperada más cercana.
        pista_midi: índice de la pista del MIDI a usar (por defecto la no percusiva con más notas).

    Devuelve `resumen` (notas, rango, porcentaje_dentro_25_cents, desviacion_media_cents con signo,
    tendencia plano/sostenido/centrado, deriva_cents entre la 1.ª y la 2.ª mitad, conteo de
    estabilidad; con MIDI además omitidas, notas_extra, notas_incorrectas, entradas
    a_tiempo/tarde/temprano, transposicion_octavas, desfase_inicio_ms y tempo_relativo >1 = más lento)
    y `notas`: t (s), dur, nota o esperada/cantada, cents (+ = sostenido), estabilidad
    (estable | vibrato con vibrato_hz y vibrato_pp_cents | inestable con desv_cents),
    deriva_cents dentro de la nota y, con MIDI, entrada_ms/entrada; las notas de la referencia
    sin cantar llevan estado=omitida y las cantadas sin pareja estado=extra. Si la lista no cabe se muestran
    las notas más problemáticas y el resto queda en `detalle_completo`.
    """
    config = cargar_config()
    return await anyio.to_thread.run_sync(
        functools.partial(
            analizar,
            audio,
            config,
            referencia_midi=referencia_midi,
            tonalidad=tonalidad,
            pista_midi=pista_midi,
        )
    )


@mcp.tool()
@_errores_legibles
async def transcribir(audio: str, idioma: str | None = None) -> str:
    """Transcribe un audio con timestamps (faster-whisper, local).

    Args:
        audio: ruta del audio o nombre devuelto por grabar_audio.
        idioma: "es", "en", "en-US", "español"…; si se omite, se detecta.

    Devuelve `idioma`, `prob_idioma`, `texto`, `segmentos` [{t, fin, texto}] y `palabras`
    [{p, t, fin}]. Si no cabe, primero se omiten palabras y luego segmentos (todo queda en
    `detalle_completo`). La primera llamada descarga el modelo (VOICE_COACH_WHISPER_MODEL).
    """
    config = cargar_config()
    return await anyio.to_thread.run_sync(analizar_transcripcion, audio, config, idioma)


@mcp.tool()
@_errores_legibles
async def metricas_discurso(audio: str, idioma: str, umbral_pausa_s: float = 0.7) -> str:
    """Mide ritmo, pausas, muletillas y variación de tono y volumen de un discurso.

    Args:
        audio: ruta del audio o nombre devuelto por grabar_audio.
        idioma: idioma del discurso ("es" o "en"; las listas de muletillas existen para ambos).
        umbral_pausa_s: silencio mínimo entre palabras para contar una pausa larga.

    Devuelve:
    - `ritmo`: palabras, tiempo_habla_s, palabras_por_minuto, ppm_sin_pausas_largas.
    - `pausas`: cantidad, total_s, max_s, por_minuto y lista [{t, dur, tras: palabra previa}].
    - `muletillas`: total, por_minuto, por_tipo y ocurrencias [{t, texto}]. Las palabras
      ambiguas ("este", "like") solo cuentan aisladas por coma o pausa.
    - `tono`: f0_mediana_hz, desv_semitonos, rango_p10_p90_semitonos, monotono (desv < 2 st) y
      tramos_monotonos [{t, fin}] en ventanas de 8 s.
    - `volumen`: media_dbfs, desv_entre_palabras_db, rango_p10_p90_db, variacion_baja (desv < 3 dB).
    - `segmentos` de la transcripción [{t, fin, texto}].
    """
    config = cargar_config()
    return await anyio.to_thread.run_sync(analizar_discurso, audio, config, idioma, umbral_pausa_s)


@mcp.prompt()
def sesion_canto(nivel: str = "intermedio", objetivo: str = "", referencia_midi: str = "") -> str:
    """Guía una sesión de canto: calentamiento, ejercicio, análisis de afinación, feedback y siguiente paso."""
    return prompts.sesion_canto(nivel, objetivo, referencia_midi)


@mcp.prompt()
def sesion_pronunciacion(nivel: str = "intermedio", foco: str = "") -> str:
    """Guía una sesión de pronunciación en inglés con pares mínimos y frases objetivo."""
    return prompts.sesion_pronunciacion(nivel, foco)


@mcp.prompt()
def sesion_oratoria(contexto: str = "", duracion_objetivo_s: int = 60) -> str:
    """Guía una sesión de oratoria: ritmo, pausas, muletillas y variación de tono y volumen."""
    return prompts.sesion_oratoria(contexto, duracion_objetivo_s)
