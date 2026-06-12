# Repository map

This file is a short orientation guide for humans and coding agents.

## What this repo does
`subtitle-fusion` aims to produce enriched subtitles from video by combining:
- dialogue transcription
- speaker reasoning
- OCR from frames
- IMDb title and character context
- SDH rules for speaker IDs and sound labels
- optional sound-event, music, and track-recognition analysis

## Where to start
Read in this order:
1. `AGENTS.md`
2. `README.md`
3. `docs/SDH_STYLE_GUIDE.md`
4. `docs/AUDIO_EVENTS_AND_MUSIC.md`
5. `src/models.py`
6. `src/pipeline.py`
7. `src/scoring.py`
8. `src/fusion.py`

## Key runtime files
- `config/settings.yaml`: global pipeline toggles and paths
- `config/scoring.yaml`: thresholds and weighting for correction decisions
- `config/style_rules.yaml`: SDH rendering policy
- `config/audio_analysis.yaml`: audio-event, music, and track-recognition policy

## Key code files
- `src/models.py`: canonical data model
- `src/scoring.py`: uncertain-word marking and review decisions
- `src/fusion.py`: evidence-based correction logic
- `src/imdb_index.py`: local IMDb TSV lookups
- `src/audio_music.py`: audio and music analysis interfaces
- `src/track_recognition.py`: ranking logic for music track candidates
- `src/exporters.py`: JSON/SRT/ASS output
- `src/pipeline.py`: orchestration and integration hooks

## Key docs
- `docs/SDH_STYLE_GUIDE.md`: when to identify speakers, when to label sounds, spoiler-safe naming
- `docs/AUDIO_EVENTS_AND_MUSIC.md`: architecture for sound events, music windows, track recognition, and lyrics

## Current architecture
The current repo is a scaffold with tested policy and scoring logic plus stub integration points.
Real providers still need to be connected for:
- ASR backend
- OCR backend
- diarization backend
- audio event detection
- music detection
- track recognition
- optional lyrics transcription

## Highest-value next steps
1. token-level replacement in `src/fusion.py`
2. apply `style_rules.yaml` inside exporters
3. wire `audio_analysis.yaml` into real provider selection
4. add provider stubs/tests before provider implementations
5. expand debug JSON with evidence traces for every correction
