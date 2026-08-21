# Repository map

This file is a short orientation guide for humans, Codex, Pi and other coding agents.

## What this repo does

`subtitle-fusion` produces enriched SDH subtitles from video by combining:

- fast ASR and word timing/alignment
- speaker diarization
- per-series voiceprints for character identity
- sparse sound-event analysis
- sparse video text detection + OCR evidence
- IMDb/title/character context
- conservative correction/fusion
- optional active-speaker visibility reasoning
- SRT, ASS and debug JSON output

## Where to start

Read in this order:

1. `AGENTS.md`
2. `README.md`
3. `docs/PIPELINE_RUNTIME.md`
4. `docs/PERFORMANCE_TARGETS.md`
5. `docs/PERFORMANCE_REFERENCES.md`
6. `docs/SDH_STYLE_GUIDE.md`
7. `docs/AUDIO_EVENTS_AND_MUSIC.md`
8. `src/models.py`
9. `src/pipeline.py`

## Performance docs

- `docs/PERFORMANCE_TARGETS.md`: current production choices, 45-minute budget, sparse-gating policy, benchmark harness contract and implementation order
- `docs/PERFORMANCE_REFERENCES.md`: external benchmark evidence, source links, papers, GitHub repos and YouTube demos

The short rule is:

```text
cheap scout -> candidate window -> stronger verifier -> fusion
```

Do not run expensive OCR, ASD or source separation over the complete episode by default.

## Key runtime/config files

- `config/settings.yaml`: global pipeline toggles, model/provider options and paths
- `config/scoring.yaml`: thresholds and weighting for correction decisions
- `config/style_rules.yaml`: SDH rendering policy
- `config/audio_analysis.yaml`: audio-event/music provider policy and thresholds

## Key code files

- `src/asr.py`: ASR adapter boundary
- `src/diarization.py`: pyannote Community-1 and interval-based speaker assignment
- `src/voiceprints.py`: per-series voice enrollment and conservative identity matching
- `src/media.py`: ffmpeg media/audio preparation
- `src/audio_music.py`: sound-event/music primitives and PANNs adapter
- `src/models.py`: canonical data model
- `src/scoring.py`: uncertain-word marking and review decisions
- `src/fusion.py`: evidence-based correction logic
- `src/imdb_index.py`: local IMDb TSV lookups
- `src/track_recognition.py`: track-candidate ranking
- `src/exporters.py`: SDH-aware JSON/SRT/ASS output
- `src/pipeline.py`: orchestration and provider integration

## Current production architecture

```text
video/audio
   |
   +--> fast ASR / alignment ----------------+
   +--> pyannote diarization ----------------+|
   +--> voiceprint identity -----------------++
   +--> sound scout -> PANNs ----------------++
   +--> sparse text scout -> selected OCR ---++
   +--> optional sparse ASD -----------------++
   +--> optional selected Demucs ------------++
                                               |
                                               v
                                      evidence fusion
                                               |
                                  debug JSON + SRT + ASS
```

The runtime adapters for ASR, diarization, voiceprints and PANNs are present. Performance-oriented visual providers remain the main next implementation area.

## Video/OCR direction

Never full-OCR all frames.

Preferred candidate order to benchmark:

1. `PP-OCRv5_mobile_det`
2. `PP-OCRv6_tiny_det`
3. OpenVINO `horizontal-text-detection-0001`
4. heavier DBNet/CRAFT/general detectors as fallbacks

Initial sampling policy:

- scene changes
- 0.5 fps periodic baseline
- temporary 2-5 fps around new/changed text tracks
- track boxes across frames
- perceptual-hash crops
- recognize only new/changed crops
- reuse cached OCR for stable tracks

## Active-speaker direction

Benchmark LR-ASD before TalkNet.

ASD must be scheduled only on speech windows and should reuse face tracks. `Segment.speaker_visible` remains tri-state (`true`, `false`, `null`); failed face detection alone must never imply off-screen speech.

## Performance objective

For a warm 45-minute episode:

- fast enriched mode target: ~1.5-3 minutes
- rich sparse-vision mode target: ~2-4 minutes

External benchmark numbers are architecture hints. Local measurements in `benchmark.json` are authoritative.

## Highest-value next steps

1. Paddle mobile/tiny text scout provider
2. text-box tracking + perceptual hash + OCR cache
3. crop-only recognizer adapter
4. local benchmark harness and regression comparison
5. cheap sound scout before PANNs verification
6. LR-ASD sparse active-speaker provider
7. selective Demucs/lyrics path
8. optimize accelerator scheduling from measured bottlenecks
