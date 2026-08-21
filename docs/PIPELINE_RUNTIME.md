# Runtime pipeline and agent handoff

## Production path

```text
video
  -> ffmpeg 16 kHz mono PCM
  -> WhisperX transcription + word alignment
  -> pyannote Community-1 diarization
  -> interval-based word/segment speaker assignment
  -> voiceprint identification
  -> PANNs AudioSet event pass
  -> sparse OpenVINO text detection -> OCR only on detected/changed crops
  -> IMDb/text fusion
  -> SDH renderer
  -> output.debug.json + output.srt + output.ass
```

Heavy ML dependencies are optional extras and are imported lazily. This keeps `pytest`, `ruff`, Codex and Pi usable on a laptop or CI runner without CUDA.

For benchmark sources, videos, and the fast-path design rationale, read `docs/PERFORMANCE_REFERENCES.md`.

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

pyannote speaker centroids are stored under `data/voiceprints/<series>.json`. On later episodes, matching is automatic when cosine similarity and margin both pass the configured thresholds.

Never force a weak match. Unknown is better than a wrong character name.

## SDH speaker-name policy

The exporter only shows an identified character label when it is useful. With `show_only_when_needed: true`, a name is shown when `speaker_visible == false`.

The active-speaker/vision provider is intentionally a separate extension point. Until LR-ASD, TalkNet, or another active-speaker detector is connected, `speaker_visible` remains unknown and names stay in debug metadata rather than being spammed on-screen.

This is deliberate: voice identity and visual visibility are different evidence.

## Audio events

PANNs runs on short overlapping windows. Only labels in `config/audio_analysis.yaml:audio_events.labels_allowlist` are emitted.

`Music` is kept separate from generic effects and becomes `MusicInfo.present`. Avoid dumping every AudioSet label into subtitles.

## Video text / OCR policy

Do **not** run full OCR on every decoded frame.

Preferred first-pass detector:

- Intel/OpenVINO `horizontal-text-detection-0001`
- model: https://docs.openvino.ai/2023.3/omz_models_model_horizontal_text_detection_0001.html
- real-time video demo: https://docs.openvino.ai/2024/openvino-workflow/model-server/ovms_demo_horizontal_text_detection.html
- OpenVINO OCR example: https://docs.openvino.ai/2024/notebooks/optical-character-recognition-with-output.html

Intel describes this model as much faster than its general text detectors. It is approximately 7.8 GFLOPs / 2.26 M parameters and is well suited to the mostly horizontal text common in TV/video: signs, lower thirds, phone/computer screens, location cards, and names.

The intended pipeline is:

```text
scene cut / sparse frame sampler
        -> horizontal-text-detection-0001
              -> no text: skip
              -> text boxes: track boxes across frames
                    -> unchanged crop: reuse cached OCR
                    -> new/changed crop: recognize only that crop
                          -> temporal voting/confidence
                          -> OCRHit evidence
```

Recognition can use OpenVINO `text-recognition-0014`, PaddleOCR/RapidOCR, or another provider. Tesseract is a fallback, not the preferred video path.

For rotated or difficult perspective text, escalate only the relevant frame/crop to a heavier detector (`text-detection-0004`, DBNet/Paddle detector, CRAFT, etc.). Never use the heavyweight fallback on every frame by default.

See `docs/PERFORMANCE_REFERENCES.md` for measured reference FPS and all external links.

## Codex / Pi work protocol

1. Read `AGENTS.md`.
2. Read this file, `docs/PERFORMANCE_REFERENCES.md`, and `docs/SDH_STYLE_GUIDE.md`.
3. Prefer provider adapters over changes to orchestration.
4. Keep heavy imports inside provider methods.
5. Add a fake-provider unit test for every orchestration change.
6. Preserve `text_raw`.
7. Do not make a speaker identity visible unless evidence is strong and story-safe.
8. Do not run expensive OCR/vision models globally when a cheap gate can narrow the work.
9. Run `pytest -q` and `ruff check .` before proposing a merge.

## Next safe extensions

- OpenVINO sparse text detector provider + crop tracker/cache + recognizer adapter
- active-speaker provider; benchmark LR-ASD first, with TalkNet as comparison
- tiny sound-event scout (for example YAMNet) before PANNs verification
- music mood classifier
- Demucs + lyric transcription only on selected vocal-music windows
- pluggable commercial track recognition
- batching/cache reuse across Sonarr/Jellyfin libraries
