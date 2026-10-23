"""Arma respuestas JSON compactas dentro de un presupuesto de bytes.

Si el resultado completo no cabe, se guarda íntegro en un JSON al lado del audio y las listas
marcadas como recortables se reducen a sus elementos más relevantes.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config


@dataclass
class Recortable:
    """Lista dentro del resultado que puede acortarse, conservando los items de mayor prioridad."""

    clave: str
    prioridad: Callable[[dict], float] = lambda _item: 0.0


def a_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def tamano(obj: Any) -> int:
    return len(a_json(obj).encode("utf-8"))


def ruta_detalle(audio: Path, tool: str, config: Config) -> Path:
    """`<audio>.<tool>.json` junto al audio; si esa carpeta no es escribible, en el dir de análisis."""
    candidata = audio.with_name(f"{audio.stem}.{tool}.json")
    if _escribible(candidata.parent):
        return candidata
    config.dir_analisis.mkdir(parents=True, exist_ok=True)
    return config.dir_analisis / candidata.name


def _escribible(carpeta: Path) -> bool:
    try:
        prueba = carpeta / ".voice-coach-prueba"
        prueba.touch()
        prueba.unlink()
        return True
    except OSError:
        return False


def _tomar(items: list[dict], n: int, prioridad: Callable[[dict], float]) -> list[dict]:
    """Los n items de mayor prioridad, en su orden original."""
    if n >= len(items):
        return items
    indices = sorted(range(len(items)), key=lambda i: prioridad(items[i]), reverse=True)[:n]
    return [items[i] for i in sorted(indices)]


def _contenedor(salida: dict, ruta: str) -> tuple[dict, str]:
    """Para "pausas.lista" devuelve (copia de salida["pausas"], "lista"), copiando por el camino."""
    *padres, clave = ruta.split(".")
    actual = salida
    for padre in padres:
        actual[padre] = dict(actual.get(padre) or {})
        actual = actual[padre]
    return actual, clave


def _recortar_lista(salida: dict, r: Recortable, limite: int) -> None:
    contenedor, clave = _contenedor(salida, r.clave)
    items = contenedor.get(clave) or []
    bajo, alto = 0, len(items)
    while bajo < alto:  # mayor n que quepa
        medio = (bajo + alto + 1) // 2
        contenedor[clave] = _tomar(items, medio, r.prioridad)
        contenedor[f"{clave}_mostradas"] = f"{medio} de {len(items)}"
        if tamano(salida) <= limite:
            bajo = medio
        else:
            alto = medio - 1
    contenedor[clave] = _tomar(items, bajo, r.prioridad)
    contenedor[f"{clave}_mostradas"] = f"{bajo} de {len(items)}"


def _recortar_texto(salida: dict, ruta: str, limite: int) -> None:
    contenedor, clave = _contenedor(salida, ruta)
    texto = contenedor.get(clave) or ""
    bajo, alto = 0, len(texto)
    while bajo < alto:
        medio = (bajo + alto + 1) // 2
        contenedor[clave] = texto[:medio] + "…"
        if tamano(salida) <= limite:
            bajo = medio
        else:
            alto = medio - 1
    contenedor[clave] = texto[:bajo] + "…"


def ajustar(
    resultado: dict,
    *,
    audio: Path,
    tool: str,
    config: Config,
    recortables: list[Recortable | str] = (),
) -> str:
    """Devuelve el JSON del resultado dentro de `config.max_bytes_respuesta`.

    Si hay que recortar, el resultado completo se escribe en disco y se indica en
    `detalle_completo`. Se recorta en el orden dado hasta que quepa: cada `Recortable` es una
    lista (admite rutas como "pausas.lista") que conserva sus items más prioritarios y queda
    marcada con `<clave>_mostradas: "n de total"`; cada `str` es la ruta de un texto que se acorta.
    """
    limite = config.max_bytes_respuesta
    if tamano(resultado) <= limite:
        return a_json(resultado)

    destino = ruta_detalle(audio, tool, config)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    salida = dict(resultado)
    salida["detalle_completo"] = str(destino)
    for r in recortables:
        if tamano(salida) <= limite:
            break
        if isinstance(r, str):
            _recortar_texto(salida, r, limite)
        else:
            _recortar_lista(salida, r, limite)
    return a_json(salida)
