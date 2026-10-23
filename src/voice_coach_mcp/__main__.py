"""Punto de entrada: `voice-coach-mcp` inicia el servidor MCP por stdio."""

import argparse
import logging
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="voice-coach-mcp", description=__doc__)
    sub = parser.add_subparsers(dest="comando")
    sub.add_parser("servidor", help="inicia el servidor MCP por stdio (por defecto)")
    args = parser.parse_args()

    # stdout es el canal del protocolo MCP: todo log va a stderr.
    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    if args.comando in (None, "servidor"):
        from .server import mcp

        mcp.run("stdio")


if __name__ == "__main__":
    main()
