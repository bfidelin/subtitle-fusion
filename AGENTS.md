# AGENTS.md

This repository is configured for Codex, Pi and other coding agents.

## Goal
Produce high-quality SDH subtitles from video by combining:
- fast ASR + word alignment
- pyannote speaker diarization
- per-series voiceprints for character identity
- AudioSet sound-event detection
- sparse video text detection + OCR / IMDb / vision evidence
- conservative text fusion
- SRT + ASS rendering

## First files to read
1. `README.md`
2. `docs/PIPELINE_RUNTIME.md`
3. `docs/PERFORMANCE_TARGETS.md`
4. `docs/PERFORMANCE_REFERENCES.md`
5. `docs/SDH_STYLE_GUIDE.md`
6. `docs/AUDIO_EVENTS_AND_MUSIC.md`
7. `config/settings.yaml`
8. `config/audio_analysis.yaml`
9. `src/models.py`
10. `src/pipeline.py`

## Architecture
- `src/asr.py`: ASR adapter; no diarization responsibility
- `src/diarization.py`: pyannote Community-1 + interval speaker assignment
- `src/voiceprints.py`: JSON voiceprint enrollment and conservative matching
- `src/audio_music.py`: PANNs event adapter and music/event primitives
- `src/media.py`: ffmpeg extraction
- `src/fusion.py`: uncertain text correction only
- `src/exporters.py`: SDH-aware JSON/SRT/ASS rendering
- `src/pipeline.py`: orchestration, not model-specific algorithms

## Performance architecture

The required pattern is:

```text
cheap scout -> candidate window -> stronger verifier -> fusion
```

Do not run an expensive provider across all media samples when a cheaper gate can narrow the work.

Current decisions:

- preserve the existing fast ASR path; use WhisperX refinement selectively when possible
- run diarization in parallel with ASR
- use a cheap sound scout before heavier PANNs verification
- never full-OCR every video frame
- benchmark `PP-OCRv5_mobile_det`, then `PP-OCRv6_tiny_det`, then OpenVINO horizontal detection for the text scout
- sample scene cuts + ~0.5 fps baseline and raise sampling temporarily around new text
- track/hash text crops and OCR only new/changed crops
- benchmark LR-ASD before TalkNet
- run ASD only on speech windows and reuse face tracks
- run Demucs only on selected vocal-music windows

Read `docs/PERFORMANCE_TARGETS.md` before changing any performance-sensitive provider or scheduling policy.

## Non-negotiable rules
- Preserve `text_raw`; never overwrite it.
- Unknown speaker identity is better than a false identity.
- Do not expose a character name before the story makes it safe.
- Voice identity does not prove on-screen visibility.
- Heavy ML imports must stay lazy so core tests work without CUDA.
- Provider changes require tests with fake/small data.
- Rich evidence belongs in `output.debug.json`; visible subtitles stay concise.
- Do not claim a performance improvement without measuring the complete affected path.

## Provider boundaries
Implement model-specific code behind adapters. Do not import WhisperX, torch, pyannote, librosa, OCR runtimes or PANNs at module import time unless unavoidable.

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

## Performance validation

Once the benchmark harness exists, performance-sensitive changes must also compare a representative episode against the previous baseline.

Required benchmark fields are specified in `docs/PERFORMANCE_TARGETS.md`, including:

- cold/warm timing
- preprocessing/inference/postprocessing split
- RTF/FPS
- p50/p95 where useful
- CPU/RAM/GPU memory peaks
- frames scanned
- OCR requests/cache hits
- ASD frames/face-track counts
- sound-verifier escalation rate
- Demucs media duration

Important-stage regressions above 10% require an explanation.

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
