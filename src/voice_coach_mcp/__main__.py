"""Punto de entrada: `voice-coach-mcp` inicia el servidor MCP por stdio."""

import argparse
import logging
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="voice-coach-mcp", description=__doc__)
    sub = parser.add_subparsers(dest="comando")
    sub.add_parser("servidor", help="inicia el servidor MCP por stdio (por defecto)")
    sub.add_parser(
        "descargar-modelos",
        help="descarga los modelos de los extras instalados para que la primera llamada sea rápida",
    )
    args = parser.parse_args()

    # stdout es el canal del protocolo MCP: todo log va a stderr.
    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    if args.comando in (None, "servidor"):
        from .server import mcp

        mcp.run("stdio")
    elif args.comando == "descargar-modelos":
        descargar_modelos()


def descargar_modelos() -> None:
    from .config import cargar_config
    from .errores import ErrorUsuario

    config = cargar_config()
    try:
        from .habla.transcripcion import modelo

        print(f"Whisper '{config.whisper_modelo}'…", file=sys.stderr)
        modelo(config)
        print("  listo", file=sys.stderr)
    except ErrorUsuario as e:
        print(f"  omitido: {e}", file=sys.stderr)
    try:
        from .pronunciacion.fonemas import esperados_por_palabra
        from .pronunciacion.wav2vec2 import MODELO, cargar_modelo

        print(f"Modelo de fonemas '{MODELO}' y espeak-ng…", file=sys.stderr)
        cargar_modelo()
        esperados_por_palabra(["hello"], "en-US")
        print("  listo", file=sys.stderr)
    except ErrorUsuario as e:
        print(f"  omitido: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
