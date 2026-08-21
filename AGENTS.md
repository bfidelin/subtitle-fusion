# AGENTS.md

This repository is configured to be easy for coding agents to navigate.

## Goal
Build a Python project that produces enriched subtitles from video by combining:
- primary ASR with timestamps and uncertainty markers
- very-fast scout ASR/OCR/audio analysis to locate difficult regions
- selective local re-ASR/review instead of expensive whole-episode reprocessing
- speaker diarization
- OCR from frames
- IMDb/show context for characters and titles
- SDH rendering rules
- optional audio-event, music, singing, lyric and track-recognition hooks
- Netflix-style French timed-text validation

## Keep this file minimal
Only put stable, high-value instructions here.
Do not duplicate detailed design docs.

## First files to read
1. `README.md`
2. `docs/FAST_SCOUT_PIPELINE.md`
3. `docs/SDH_STYLE_GUIDE.md`
4. `docs/NETFLIX_FR_STYLE.md`
5. `docs/AUDIO_EVENTS_AND_MUSIC.md`
6. `config/scoring.yaml`
7. `config/style_rules.yaml`
8. `config/audio_analysis.yaml`
9. `src/models.py`
10. `src/pipeline.py`
11. `src/fusion.py`
12. `src/scoring.py`

## Repository map
- `src/models.py`: core data classes for segments, words, decisions, and pipeline results
- `src/scoring.py`: confidence thresholds and uncertain-word marking
- `src/fusion.py`: candidate scoring and correction decisions
- `src/imdb_index.py`: local IMDb TSV loading and candidate extraction
- `src/audio_music.py`: audio event and music analysis interfaces
- `src/track_recognition.py`: ranking of track candidates using multiple signals
- `src/netflix_style.py`: Netflix-style French layout/timing validation
- `src/exporters.py`: JSON, SRT, and ASS output
- `src/pipeline.py`: orchestration and future integration points
- `docs/FAST_SCOUT_PIPELINE.md`: fast scouts, evidence timeline, confidence router, selective escalation and backend strategy
- `docs/`: style and architecture guidance
- `config/`: runtime policy and thresholds
- `tests/`: unit tests

## Working rules
- Preserve `text_raw`; never overwrite it.
- Put corrections in `text_corrected` and `decision`.
- Only auto-correct uncertain content when evidence is strong.
- Confidence controls compute cost: expensive processing should be selective and local.
- Prefer cheap whole-episode scouts over expensive whole-episode second passes.
- Keep ASR/OCR/audio/source-separation providers behind replaceable adapters.
- Prefer character names over actor names in visible subtitle text.
- Do not reveal names before the story reveals them.
- Keep visible SDH output concise.
- Store rich evidence in debug JSON rather than in visible subtitles.
- The Netflix formatter may change layout/timing safely but must never invent, truncate or paraphrase dialogue silently.

## Evidence priority
Use this order when resolving uncertain tokens:
1. OCR explicit on-screen text
2. IMDb character match restricted to current title/episode
3. names already validated in show/episode glossary
4. dialogue context
5. actor/face hint
6. phonetic similarity

A disagreement between a cheap scout ASR and the primary ASR is an escalation signal, not an automatic correction.

## Confidence policy
Keep evidence dimensions explainable where practical rather than collapsing them into one opaque score:
- ASR confidence
- scout agreement
- OCR confidence
- proper-name confidence
- context confidence
- translation confidence
- linguistic QA confidence
- final routing/decision confidence

## Audio and music policy
- Treat sound-event detection, music detection, singing detection, track recognition, source separation and lyric transcription as separate tasks.
- Run cheap event/music scouts over the episode.
- Run Demucs/source separation only on selected windows where it can improve lyrics/dialogue.
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

## Preferred implementation order
1. ingest real Faster-Whisper word/timestamp/confidence data
2. add evidence timeline + confidence router
3. add local audio crop + selective re-ASR
4. wire fast OCR detection/region recognition
5. add show/episode proper-name glossary persistence
6. add Moonshine-style scout ASR adapter
7. add audio-event/music/singing routing
8. add selective Demucs + vocal ASR
9. add translation + grammar/spelling/context reviewer
10. add shot-aware Netflix timing
11. profile and calibrate thresholds on real episodes

## Avoid
- large speculative rewrites
- expensive whole-episode processing when a local window is sufficient
- coupling core semantics to one hardware/backend provider
- changing output semantics without updating docs and tests
- adding long, stale instructions to this file
