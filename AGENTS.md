# AGENTS.md

This repository is configured for Codex, Pi and other coding agents.

## Goal
Produce high-quality SDH subtitles from video by combining:
- WhisperX ASR + word alignment
- pyannote speaker diarization
- per-series voiceprints for character identity
- AudioSet sound-event detection
- OCR / IMDb / vision evidence
- conservative text fusion
- SRT + ASS rendering

## First files to read
1. `README.md`
2. `docs/PIPELINE_RUNTIME.md`
3. `docs/SDH_STYLE_GUIDE.md`
4. `docs/AUDIO_EVENTS_AND_MUSIC.md`
5. `config/settings.yaml`
6. `config/audio_analysis.yaml`
7. `src/models.py`
8. `src/pipeline.py`

## Architecture
- `src/asr.py`: WhisperX adapter; no diarization responsibility
- `src/diarization.py`: pyannote Community-1 + interval speaker assignment
- `src/voiceprints.py`: JSON voiceprint enrollment and conservative matching
- `src/audio_music.py`: PANNs event adapter and music/event primitives
- `src/media.py`: ffmpeg extraction
- `src/fusion.py`: uncertain text correction only
- `src/exporters.py`: SDH-aware JSON/SRT/ASS rendering
- `src/pipeline.py`: orchestration, not model-specific algorithms

## Non-negotiable rules
- Preserve `text_raw`; never overwrite it.
- Unknown speaker identity is better than a false identity.
- Do not expose a character name before the story makes it safe.
- Voice identity does not prove on-screen visibility.
- Heavy ML imports must stay lazy so core tests work without CUDA.
- Provider changes require tests with fake/small data.
- Rich evidence belongs in `output.debug.json`; visible subtitles stay concise.

## Provider boundaries
Implement model-specific code behind adapters. Do not import WhisperX, torch, pyannote, librosa or PANNs at module import time unless unavoidable.

## Validation
```bash
pip install -e '.[dev]'
pytest -q
ruff check .
```

GPU smoke test:
```bash
pip install -e '.[runtime]'
export HUGGINGFACE_TOKEN=...
subtitle-fusion run \
  --video /path/episode.mkv \
  --title "Example Show" \
  --season 1 \
  --episode 1 \
  --output-dir /tmp/subtitle-fusion-out
```

## Voice enrollment workflow
Inspect the first episode debug JSON, create:

```yaml
SPEAKER_00: Character Name
SPEAKER_01: Another Character
```

Run again with `--speaker-map`. The embeddings are enrolled for future episodes.

## Active-speaker / off-screen work
The data model already exposes `Segment.speaker_visible`.
An active-speaker provider must only set:
- `true`: matched speaking face visible
- `false`: identified voice is speaking but no matched active face is visible
- `null`: insufficient evidence

Do not infer `false` merely because face detection failed.

## Agent skill
Read `skills/repo-navigation/SKILL.md` for task-specific entry points.
