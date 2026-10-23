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


def ajustar(
    resultado: dict,
    *,
    audio: Path,
    tool: str,
    config: Config,
    recortables: list[Recortable] = (),
) -> str:
    """Devuelve el JSON del resultado dentro de `config.max_bytes_respuesta`.

    Si hay que recortar, el resultado completo se escribe en disco y se indica en
    `detalle_completo`; cada lista recortada lleva `<clave>_mostradas: "n de total"`.
    """
    limite = config.max_bytes_respuesta
    if tamano(resultado) <= limite:
        return a_json(resultado)

    destino = ruta_detalle(audio, tool, config)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    salida = dict(resultado)
    salida["detalle_completo"] = str(destino)
    originales = {r.clave: resultado.get(r.clave) or [] for r in recortables}
    for r in recortables:
        salida[f"{r.clave}_mostradas"] = f"{len(originales[r.clave])} de {len(originales[r.clave])}"

    # Recorta las listas en orden: la primera se reduce primero; se busca el mayor n que quepa.
    for r in recortables:
        items = originales[r.clave]
        if tamano(salida) <= limite:
            break
        bajo, alto = 0, len(items)
        while bajo < alto:
            medio = (bajo + alto + 1) // 2
            salida[r.clave] = _tomar(items, medio, r.prioridad)
            salida[f"{r.clave}_mostradas"] = f"{medio} de {len(items)}"
            if tamano(salida) <= limite:
                bajo = medio
            else:
                alto = medio - 1
        salida[r.clave] = _tomar(items, bajo, r.prioridad)
        salida[f"{r.clave}_mostradas"] = f"{bajo} de {len(items)}"
    return a_json(salida)
