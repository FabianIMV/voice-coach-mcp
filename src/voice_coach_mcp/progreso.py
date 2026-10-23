"""Registro de progreso en un markdown local (~/VoiceCoach/progreso.md).

Solo guarda y lee entradas: el contenido lo redacta Claude. Existe como tool para que el
registro funcione también en clientes sin acceso al sistema de archivos (Claude Desktop).
"""

import re
from datetime import datetime
from pathlib import Path

from .config import Config
from .errores import ErrorUsuario
from .salida import tamano

ENCABEZADO = "# Progreso de voz\n\nRegistro de sesiones con voice-coach-mcp. Cada sesión es una sección `## `.\n"
MAX_ENTRADA = 4000


def ruta(config: Config) -> Path:
    return config.dir_base / "progreso.md"


def _entradas(texto: str) -> list[str]:
    partes = re.split(r"(?m)^(?=## )", texto)
    return [p.strip() for p in partes if p.startswith("## ")]


def leer(config: Config, entradas: int = 5) -> dict:
    archivo = ruta(config)
    if not archivo.exists():
        return {"archivo": str(archivo), "entradas_totales": 0, "entradas": []}
    todas = _entradas(archivo.read_text(encoding="utf-8"))
    ultimas = todas[-max(1, entradas) :]
    resultado = {
        "archivo": str(archivo),
        "entradas_totales": len(todas),
        "entradas_mostradas": len(ultimas),
        "entradas": ultimas,
    }
    # Si no caben, se descartan primero las más antiguas.
    while len(resultado["entradas"]) > 1 and tamano(resultado) > config.max_bytes_respuesta:
        resultado["entradas"] = resultado["entradas"][1:]
        resultado["entradas_mostradas"] = len(resultado["entradas"])
    return resultado


def registrar(config: Config, entrada: str) -> dict:
    texto = entrada.strip()
    if not texto:
        raise ErrorUsuario("La entrada está vacía.")
    if len(texto) > MAX_ENTRADA:
        raise ErrorUsuario(f"La entrada supera {MAX_ENTRADA} caracteres; resúmela.")
    if not texto.startswith("## "):
        texto = f"## {datetime.now():%Y-%m-%d %H:%M}\n\n{texto}"
    archivo = ruta(config)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    previo = archivo.read_text(encoding="utf-8") if archivo.exists() else ENCABEZADO
    archivo.write_text(previo.rstrip() + "\n\n" + texto + "\n", encoding="utf-8")
    return {
        "archivo": str(archivo),
        "entradas_totales": len(_entradas(archivo.read_text(encoding="utf-8"))),
    }
