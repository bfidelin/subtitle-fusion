# subtitle-fusion

Production-oriented Python pipeline for **enriched SDH subtitles**.

It combines:
- fast ASR / WhisperX alignment
- pyannote `speaker-diarization-community-1`
- per-series speaker embeddings / voiceprints
- sound-event scout + PANNs verification
- sparse video text detection + OCR evidence
- IMDb context and conservative text correction
- SDH rendering to SRT and ASS

## Status

The repository has a real runtime path. Heavy ML dependencies are optional extras and loaded lazily, so agents and CI can work on the core without a GPU.

```text
video
  -> ffmpeg
  -> ASR / WhisperX alignment
  -> pyannote Community-1
  -> speaker assignment
  -> voiceprint identity
  -> sound scout -> PANNs audio events/music
  -> sparse text scout -> OCR only on useful crops
  -> IMDb/text fusion
  -> SDH SRT + ASS + debug JSON
```

See:
- `docs/PIPELINE_RUNTIME.md` for runtime and Codex/Pi handoff
- `docs/PERFORMANCE_TARGETS.md` for current production choices, the 45-minute budget and benchmark-harness contract
- `docs/PERFORMANCE_REFERENCES.md` for the full benchmark evidence, source URLs, papers and YouTube demos

## Install

Core + tests:

```bash
pip install -e '.[dev]'
pytest -q
```

Full ML runtime:

```bash
pip install -e '.[runtime]'
```

You also need `ffmpeg`.

For pyannote Community-1:

```bash
export HUGGINGFACE_TOKEN=...
```

after accepting the model conditions on Hugging Face.

## Run

```bash
subtitle-fusion run \
  --video /path/video.mkv \
  --title "Example Show" \
  --season 1 \
  --episode 3 \
  --imdb-title-id tt1234567 \
  --output-dir ./out
```

Outputs:
- `output.debug.json`
- `output.srt`
- `output.ass`

## Learn character voices

After the first run, inspect diarization IDs and create `speaker-map.yaml`:

```yaml
SPEAKER_00: Carrie
SPEAKER_01: Saul
```

Then run:

```bash
subtitle-fusion run \
  --video episode01.mkv \
  --title "Homeland" \
  --speaker-map speaker-map.yaml \
  --output-dir out/episode01
```

The pyannote speaker embedding is enrolled in `data/voiceprints/<series>.json`. Later episodes are matched automatically using cosine similarity plus a minimum margin over the second-best character. Weak matches remain unknown.

## SDH behavior

Examples:

```text
[door]

Where are you?
```

When an active-speaker/vision adapter establishes that an identified character is speaking off-screen:

```text
Carrie: Where are you?
```

Music is treated separately:

```text
♪ musique ♪
```

Debug metadata can be rich; visible subtitles should stay readable.

## Fast video text strategy

Full OCR on every frame is explicitly rejected.

Current scout candidates, in benchmark order to test locally:

1. **PaddleOCR `PP-OCRv5_mobile_det`** — official T4 high-performance inference: **6.36 ms/image**, CPU high-performance: **28.15 ms/image**.
2. **`PP-OCRv6_tiny_det`** — 0.43M parameters / 1.9 MB; benchmark locally because current official timing uses A100.
3. **OpenVINO `horizontal-text-detection-0001`** — excellent horizontal specialist; official async video demo around **25.6 FPS** at 704x704.

Start with scene cuts + about **0.5 fps** periodic detection, track boxes, hash crops, and OCR only new/changed text. For a 45-minute episode that periodic baseline is only 1,350 frames instead of 67,500 frames at 25 fps.

At the published PP-OCRv5 mobile T4 detector rate, those 1,350 baseline frames correspond to only about **9 seconds of detector inference**. The expensive part is recognition, which is why crop tracking/cache is mandatory.

The warm production target is approximately:

- **1.5-3 minutes** for fast enriched mode
- **2-4 minutes** for rich mode with sparse visual analysis

These are engineering targets; local `benchmark.json` measurements are authoritative.

See `docs/PERFORMANCE_TARGETS.md` for the full budget and `docs/PERFORMANCE_REFERENCES.md` for exact hardware/caveats.

## Agent-friendly repository

- `AGENTS.md` contains stable coding and performance rules.
- `skills/repo-navigation/SKILL.md` routes Codex/Pi by task.
- `docs/PIPELINE_RUNTIME.md` describes provider boundaries and handoff.
- `docs/PERFORMANCE_TARGETS.md` records current tool choices, sparse scheduling and benchmark requirements.
- `docs/PERFORMANCE_REFERENCES.md` documents external performance evidence and links.
- heavy ML imports are lazy.
- pure orchestration helpers have unit tests.

## Important design rules

- raw ASR is always preserved
- uncertain text is corrected only with strong evidence
- character identity and visual visibility are separate evidence
- character names must be story-safe
- only plot-relevant sound events should reach visible subtitles
- expensive video/audio models should be gated by cheap detectors whenever possible
- local measured p50/p95 timing is the authority over external benchmark projections

## Next extensions

1. Paddle mobile/tiny text scout + text-track cache + recognizer adapter
2. Local benchmark harness and `benchmark.json`
3. Active-speaker detection, benchmarking LR-ASD before TalkNet
4. Tiny sound-event scout before heavier PANNs verification
5. Selective Demucs/lyrics path
