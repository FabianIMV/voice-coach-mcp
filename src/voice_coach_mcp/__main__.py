"""Entry point: `voice-coach-mcp` starts the MCP server over stdio."""

import argparse
import logging
import sys
from importlib import resources
from pathlib import Path

SKILL_NAME = "voice-coach"


def main() -> None:
    parser = argparse.ArgumentParser(prog="voice-coach-mcp", description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="start the MCP server over stdio (default)")
    sub.add_parser(
        "download-models",
        help="download the models of the installed extras so the first call is fast",
    )
    package = sub.add_parser(
        "package-skill", help=f"create a .zip of the {SKILL_NAME} skill for Claude Desktop"
    )
    package.add_argument("destination", nargs="?", default=f"{SKILL_NAME}.zip")
    args = parser.parse_args()

    # stdout is the MCP protocol channel: every log goes to stderr. Libraries (httpx,
    # huggingface_hub…) only show warnings; the server also shows its INFO messages.
    logging.basicConfig(
        stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("voice_coach_mcp").setLevel(logging.INFO)

    if args.command in (None, "serve"):
        from .server import mcp

        mcp.run("stdio")
    elif args.command == "download-models":
        download_models()
    elif args.command == "package-skill":
        print(package_skill(Path(args.destination)), file=sys.stderr)


def skill_dir() -> Path:
    """The skill bundled in the package (wheel install) or in the repository (source checkout)."""
    bundled = resources.files(__package__) / "_skill" / SKILL_NAME
    if bundled.is_dir():
        return Path(str(bundled))
    return Path(__file__).resolve().parents[2] / "skills" / SKILL_NAME


def package_skill(destination: Path) -> Path:
    """Zip with the voice-coach/ folder at its root, as Claude Desktop expects."""
    import zipfile

    source = skill_dir()
    if not (source / "SKILL.md").exists():
        raise SystemExit(f"Skill not found at {source}")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted(source.rglob("*")):
            if file.is_file():
                z.write(file, Path(SKILL_NAME) / file.relative_to(source))
    return destination.resolve()


def download_models() -> None:
    from .config import load_config
    from .errors import UserError

    config = load_config()
    try:
        from .speech.transcription import model

        print(f"Whisper '{config.whisper_model}'…", file=sys.stderr)
        model(config)
        print("  ready", file=sys.stderr)
    except UserError as e:
        print(f"  skipped: {e}", file=sys.stderr)
    try:
        from .pronunciation.phonemes import expected_by_word
        from .pronunciation.wav2vec2 import MODEL, load_model

        print(f"Phoneme model '{MODEL}' and espeak-ng…", file=sys.stderr)
        load_model()
        expected_by_word(["hello"], "en-US")
        print("  ready", file=sys.stderr)
    except UserError as e:
        print(f"  skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
