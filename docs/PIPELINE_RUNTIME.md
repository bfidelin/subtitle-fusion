# Runtime pipeline and agent handoff

## Production path

```text
video
  -> ffmpeg 16 kHz mono PCM
  -> fast ASR / WhisperX alignment when needed
  -> pyannote Community-1 diarization
  -> interval-based word/segment speaker assignment
  -> voiceprint identification
  -> sound scout -> PANNs verifier
  -> sparse video text scout -> OCR only on detected/changed crops
  -> IMDb/text fusion
  -> SDH renderer
  -> output.debug.json + output.srt + output.ass
```

Heavy ML dependencies are optional extras and imported lazily. This keeps `pytest`, `ruff`, Codex and Pi usable without CUDA.

For benchmark sources, videos, and performance rationale, read `docs/PERFORMANCE_REFERENCES.md`.

## Install

Core/dev only:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

GPU runtime:

```bash
pip install -e '.[runtime]'
```

`ffmpeg` must be installed separately.

For pyannote Community-1, accept the model conditions on Hugging Face and export:

```bash
export HUGGINGFACE_TOKEN=...
```

## First episode: enroll character voices

Run once with a small YAML mapping produced after inspecting `output.debug.json`:

```yaml
SPEAKER_00: Carrie
SPEAKER_01: Saul
SPEAKER_02: Quinn
```

Then:

```bash
subtitle-fusion run \
  --video episode01.mkv \
  --title "Homeland" \
  --season 1 \
  --episode 1 \
  --speaker-map speaker-map.yaml \
  --output-dir out/s01e01
```

pyannote speaker centroids are stored under `data/voiceprints/<series>.json`. On later episodes, matching is automatic when cosine similarity and margin both pass configured thresholds.

Never force a weak match. Unknown is better than a wrong character name.

## SDH speaker-name policy

The exporter only shows an identified character label when it is useful. With `show_only_when_needed: true`, a name is shown when `speaker_visible == false`.

The active-speaker/vision provider is intentionally separate. Until LR-ASD, TalkNet, or another ASD detector is connected, `speaker_visible` remains unknown and names stay in debug metadata rather than being spammed on-screen.

Voice identity and visual visibility are different evidence.

## Audio events

Use a cheap sound-event scout first. Escalate candidate/uncertain windows to PANNs.

Only labels in `config/audio_analysis.yaml:audio_events.labels_allowlist` should be emitted. `Music` stays separate from generic effects and becomes `MusicInfo.present`.

## Video text / OCR policy

Do **not** run full OCR on every decoded frame.

### Preferred scout order

1. `PP-OCRv5_mobile_det` — current strongest published speed evidence for a general text detector:
   - T4: **6.36 ms/image** high-performance model inference
   - Xeon Gold 6271C: **28.15 ms/image** high-performance model inference
   - 4.7 MB model
   - source: https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_detection.en.md
2. `PP-OCRv6_tiny_det` — next-generation ultra-light candidate:
   - 0.43M parameters / 1.9 MB
   - current A100 + ONNXRuntime reference: 20.49 ms/image end-to-end
   - benchmark locally before preferring it over v5 because the official test hardware differs
3. Intel/OpenVINO `horizontal-text-detection-0001` — excellent horizontal specialist:
   - ~7.78 GFLOPs / ~2.26M parameters
   - official async client/server demo around 25.6 FPS at 704x704
   - https://docs.openvino.ai/2023.3/omz_models_model_horizontal_text_detection_0001.html
   - https://docs.openvino.ai/2024/openvino-workflow/model-server/ovms_demo_horizontal_text_detection.html
4. heavier DB/CRAFT/general detectors only as fallback.

### Initial sampling policy

For a 45-minute episode, start with:

- scene-change frames
- plus **0.5 fps** periodic sampling
- raise temporarily to 2-5 fps around a newly detected text track

At 0.5 fps there are only 1,350 periodic frames instead of 67,500 frames at 25 fps.

The intended pipeline is:

```text
scene cuts + 0.5 fps baseline
        -> fast text scout
              -> no text: skip
              -> text boxes: track across frames
                    -> unchanged crop: reuse cached OCR
                    -> new/changed crop: recognize only that crop
                          -> temporal voting/confidence
                          -> OCRHit evidence
```

Recognition can use OpenVINO `text-recognition-0014`, Paddle/RapidOCR, or another provider. Tesseract is compatibility fallback only.

For rotated/perspective-heavy text, escalate only the relevant frame/crop to a stronger detector. Never run heavyweight detection or recognition over the whole episode by default.

## Active-speaker policy

Benchmark LR-ASD first because it is far lighter than TalkNet while retaining strong AVA accuracy. However, **model FLOPs are not the whole ASD cost**: face detection, tracking, decoding and buffering dominate many end-to-end pipelines.

Run ASD only:

- inside known speech windows
- on reused face tracks
- at reduced/smart frame rates when accuracy permits

Never scan every video frame by default.

## Codex / Pi work protocol

1. Read `AGENTS.md`.
2. Read this file, `docs/PERFORMANCE_REFERENCES.md`, and `docs/SDH_STYLE_GUIDE.md`.
3. Prefer provider adapters over orchestration rewrites.
4. Keep heavy imports inside provider methods.
5. Add a fake-provider unit test for orchestration changes.
6. Preserve `text_raw`.
7. Do not make speaker identity visible unless evidence is strong and story-safe.
8. Gate expensive OCR/vision/audio models with cheap scouts.
9. Record cold/warm timing, RTF/FPS, memory and cache hit rate for local provider benchmarks.
10. Run `pytest -q` and `ruff check .` before proposing a merge.

## Next safe extensions

- `PP-OCRv5_mobile_det` / `PP-OCRv6_tiny_det` scout provider + crop tracker/cache + recognizer adapter
- active-speaker provider; benchmark LR-ASD first, TalkNet as comparison
- tiny sound-event scout before PANNs verification
- local benchmark harness with per-provider p50/p95 timings
- music mood classifier
- Demucs + lyric transcription only on selected vocal-music windows
- pluggable commercial track recognition
- batching/cache reuse across media libraries
