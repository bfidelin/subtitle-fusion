# Repo navigation skill

## Purpose
Help Codex, Pi, or another coding agent make safe changes quickly.

## Fast entry
1. `AGENTS.md`
2. `docs/PIPELINE_RUNTIME.md`
3. `docs/PERFORMANCE_TARGETS.md`
4. `README.md`
5. the relevant policy/config
6. implementation + matching tests

Use `docs/PERFORMANCE_REFERENCES.md` when a task involves model choice, speed claims, benchmark interpretation, device placement or sampling policy.

## Task routes

### ASR / timestamps
Read:
- `src/asr.py`
- `src/media.py`
- `src/models.py`
- `config/settings.yaml`
- `docs/PERFORMANCE_TARGETS.md`

Keep heavy imports lazy. ASR must not own speaker identity. Preserve the fast ASR path and avoid unnecessary full retranscription.

### Diarization / speaker assignment
Read:
- `src/diarization.py`
- `src/voiceprints.py`
- `tests/test_diarization.py`
- `tests/test_voiceprints.py`
- `docs/PERFORMANCE_TARGETS.md`

Community-1 returns speaker embeddings. Preserve raw `SPEAKER_*` IDs in debug data. Prefer parallel scheduling with ASR where resources permit.

### Character names / voiceprints
Read:
- `src/voiceprints.py`
- `docs/PIPELINE_RUNTIME.md`
- `config/settings.yaml`

Never force a match below both score and margin thresholds.

### SDH / off-screen labels
Read:
- `src/exporters.py`
- `config/style_rules.yaml`
- `docs/SDH_STYLE_GUIDE.md`
- `tests/test_exporters_sdh.py`

Voice identity is not visibility. Only an active-speaker/vision provider may set `speaker_visible`.

### Active speaker / visual visibility
Read:
- `src/models.py`
- `docs/PIPELINE_RUNTIME.md`
- `docs/PERFORMANCE_TARGETS.md`
- `docs/PERFORMANCE_REFERENCES.md`

Benchmark LR-ASD before TalkNet. Do not analyze every frame. Schedule on speech windows, reuse face tracks and start with sparse visual sampling. Never infer off-screen from a failed face detector alone.

### Video text / OCR
Read:
- `docs/PERFORMANCE_TARGETS.md`
- `docs/PERFORMANCE_REFERENCES.md`
- `src/models.py`
- `src/pipeline.py`

Current scout order to benchmark locally:
1. `PP-OCRv5_mobile_det`
2. `PP-OCRv6_tiny_det`
3. OpenVINO `horizontal-text-detection-0001`

Required architecture:

```text
scene cuts + sparse samples
  -> cheap text detector
  -> track boxes
  -> perceptual hash
  -> OCR only new/changed crops
  -> temporal voting
```

Full OCR on every frame is forbidden as a default path.

### Audio events / music
Read:
- `src/audio_music.py`
- `config/audio_analysis.yaml`
- `docs/AUDIO_EVENTS_AND_MUSIC.md`
- `docs/PERFORMANCE_TARGETS.md`

Prefer a cheap scout before heavier PANNs verification. Keep a small visible-event allowlist and merge repeated windows.

### Demucs / lyrics
Read:
- `docs/AUDIO_EVENTS_AND_MUSIC.md`
- `docs/PERFORMANCE_TARGETS.md`
- `docs/PERFORMANCE_REFERENCES.md`

Source separation is only for selected vocal-music windows. Never run Demucs over the complete episode by default.

### Text correction
Read:
- `src/scoring.py`
- `src/fusion.py`
- `src/imdb_index.py`
- matching tests

Never overwrite `text_raw`.

### Performance / benchmark harness
Read:
- `docs/PERFORMANCE_TARGETS.md`
- `docs/PERFORMANCE_REFERENCES.md`
- `src/pipeline.py`

The harness must measure cold/warm time, preprocessing/inference/postprocessing, RTF/FPS, p50/p95 when useful, memory peaks, and stage-specific gating/cache counters. Local measurements override external projections.

## Validation
```bash
pip install -e '.[dev]'
pytest -q
ruff check .
```

For model-level smoke tests:
```bash
pip install -e '.[runtime]'
export HUGGINGFACE_TOKEN=...
```

## Definition of done
- behavior covered by tests
- configs/docs updated with semantics
- no eager heavy-model import
- debug JSON preserves evidence
- SRT/ASS remain concise
- no performance claim without measured or cited evidence
- performance-sensitive changes include a local benchmark when the heavy runtime is available
