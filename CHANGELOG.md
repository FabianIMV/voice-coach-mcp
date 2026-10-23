# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-10-23

### Changed

- The Claude Code plugin and the MCPB extension start the server with `uv run --frozen`, so the
  dependencies always come from `uv.lock` (required by the Claude plugin directory).
- Dropped the CPU-only PyTorch index from `pyproject.toml`: every dependency now comes from PyPI.
- README: privacy and network access section; absolute links and image so it renders on PyPI.

## [0.1.0] - 2026-10-23

### Added

- `record_audio`: microphone recording to 16 kHz mono WAV with macOS microphone-permission detection.
- `analyze_pitch`: pitch accuracy against equal temperament, a key or a MIDI reference melody
  (octave shift, start offset, relative tempo, missed/extra/wrong notes, late/early onsets,
  stability and vibrato).
- `transcribe`: local transcription with faster-whisper and word-level timestamps.
- `speech_metrics`: pace, energy-based long pauses, filler words (English and Spanish lists),
  pitch monotony and volume variation.
- `assess_pronunciation`: phoneme-level English pronunciation assessment with a local wav2vec2
  phoneme model, with an optional Azure Pronunciation Assessment backend.
- `read_progress` and `log_progress`: a local markdown progress log.
- MCP prompts `singing_session`, `pronunciation_session` and `speaking_session`.
- `voice-coach` skill with session structure, feedback rules and per-mode references.
- Distribution as a PyPI package, a Claude Code plugin marketplace, a Claude Desktop extension
  (`.mcpb`) and an MCP Registry entry.

[Unreleased]: https://github.com/FabianIMV/voice-coach-mcp/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/FabianIMV/voice-coach-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/FabianIMV/voice-coach-mcp/releases/tag/v0.1.0
