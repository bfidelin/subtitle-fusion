# AGENTS.md

This repository is configured to be easy for coding agents to navigate.

## Goal
Build a Python project that produces enriched subtitles from video by combining:
- ASR with timestamps and uncertainty markers
- speaker diarization
- OCR from frames
- IMDb context for characters and titles
- SDH rendering rules
- optional audio-event, music, and track-recognition hooks

## Keep this file minimal
Only put stable, high-value instructions here.
Do not duplicate detailed design docs.

## First files to read
1. `README.md`
2. `docs/SDH_STYLE_GUIDE.md`
3. `docs/AUDIO_EVENTS_AND_MUSIC.md`
4. `config/scoring.yaml`
5. `config/style_rules.yaml`
6. `config/audio_analysis.yaml`
7. `src/models.py`
8. `src/pipeline.py`
9. `src/fusion.py`
10. `src/scoring.py`

## Repository map
- `src/models.py`: core data classes for segments, words, decisions, and pipeline results
- `src/scoring.py`: confidence thresholds and uncertain-word marking
- `src/fusion.py`: candidate scoring and correction decisions
- `src/imdb_index.py`: local IMDb TSV loading and candidate extraction
- `src/audio_music.py`: audio event and music analysis interfaces
- `src/track_recognition.py`: ranking of track candidates using multiple signals
- `src/exporters.py`: JSON, SRT, and ASS output
- `src/pipeline.py`: orchestration and future integration points
- `docs/`: style and architecture guidance
- `config/`: runtime policy and thresholds
- `tests/`: unit tests

## Working rules
- Preserve `text_raw`; never overwrite it.
- Put corrections in `text_corrected` and `decision`.
- Only auto-correct uncertain content when evidence is strong.
- Prefer character names over actor names in visible subtitle text.
- Do not reveal names before the story reveals them.
- Keep visible SDH output concise.
- Store rich evidence in debug JSON rather than in visible subtitles.

## Evidence priority
Use this order when resolving uncertain tokens:
1. OCR explicit on-screen text
2. IMDb character match restricted to current title/episode
3. dialogue context
4. actor/face hint
5. phonetic similarity

## Audio and music policy
- Treat sound-event detection, music detection, track recognition, and lyric transcription as separate tasks.
- Use lyrics and musical signals to rerank track candidates, not as a blind replacement for recognition.
- Keep commercial track identification mostly in metadata by default.

## Test commands
```bash
pip install -e .[dev]
pytest -q
```

## Local smoke test
```bash
subtitle-fusion run \
  --video /tmp/fake-video.mkv \
  --title "Example Show" \
  --season 1 \
  --episode 3 \
  --imdb-title-id tt1234567 \
  --output-dir /tmp/subtitle-fusion-out
```

## Preferred kind of changes
Good next changes:
- connect uncertain-word markers directly into token-level replacement in `fusion.py`
- wire `style_rules.yaml` into `exporters.py`
- wire `audio_analysis.yaml` into provider selection
- add provider stubs and tests before real integrations

## Avoid
- large speculative rewrites
- changing output semantics without updating docs and tests
- adding long, stale instructions to this file
