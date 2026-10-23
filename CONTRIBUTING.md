# Contributing

Thanks for your interest in improving voice-coach-mcp! Issues and pull requests are welcome.

## Development setup

```bash
git clone https://github.com/FabianIMV/voice-coach-mcp.git
cd voice-coach-mcp
uv sync --extra speech --extra pronunciation
```

System dependencies: `espeak-ng` (pronunciation) and, optionally, `ffmpeg` (m4a/aac input).
On macOS: `brew install espeak-ng ffmpeg`. On Debian/Ubuntu: `sudo apt install espeak-ng ffmpeg libportaudio2`.

## Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest                  # fast suite: synthetic audio, simulated microphone
uv run pytest -m models        # real models (Whisper tiny, wav2vec2) on synthetic speech
```

The fast suite must stay green on every pull request; the `models` suite runs in CI too.

## Design principles

- **Tools measure, Claude interprets.** Tool outputs are numbers and descriptive categories,
  never advice. Coaching lives in the `skills/voice-coach` skill and the MCP prompts.
- **Compact responses.** Every tool response stays under ~2 KB; longer details go to a JSON file
  next to the audio (`output.fit`).
- **Every response carries `confidence` and `warnings`.**
- **Local first.** Audio never leaves the machine unless the user opts into the Azure backend.
- **No copyrighted material.** Tests and examples use synthetic audio and MIDI only.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`,
`test:`, `chore:`…) and keep the `CHANGELOG.md` `Unreleased` section up to date.

## Releasing

1. Bump the version in `pyproject.toml`, `src/voice_coach_mcp/__init__.py`, `manifest.json`,
   `server.json` and `.claude-plugin/plugin.json`, and move the changelog entries under the new version.
2. Tag `vX.Y.Z` and push the tag: the `release` workflow builds and publishes the package to
   PyPI, builds the `.mcpb` and the skill zip, and attaches them to a GitHub release.
3. Run `mcp-publisher publish` to update the MCP Registry entry.
