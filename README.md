# subtitle-fusion

Production-oriented Python pipeline for **enriched SDH subtitles**.

It combines:
- WhisperX ASR with word timestamps
- pyannote `speaker-diarization-community-1`
- per-series speaker embeddings / voiceprints
- PANNs AudioSet sound-event classification
- sparse video text detection + OCR evidence
- IMDb context and conservative text correction
- SDH rendering to SRT and ASS

## Status

The repository now has a real runtime path. Heavy ML dependencies are optional extras and loaded lazily, so agents and CI can work on the core without a GPU.

```text
video
  -> ffmpeg
  -> WhisperX
  -> pyannote Community-1
  -> speaker assignment
  -> voiceprint identity
  -> PANNs audio events/music
  -> sparse OpenVINO text detection -> OCR only on useful crops
  -> IMDb/text fusion
  -> SDH SRT + ASS + debug JSON
```

See:
- `docs/PIPELINE_RUNTIME.md` for the detailed runtime and Codex/Pi handoff
- `docs/PERFORMANCE_REFERENCES.md` for benchmark sources, YouTube demos, and the fast-path design

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

After the first run, inspect the diarization IDs and create `speaker-map.yaml`:

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

The current pyannote speaker embedding is enrolled in `data/voiceprints/<series>.json`. Later episodes are matched automatically using cosine similarity **plus a minimum margin over the second-best character**.

Weak matches remain unknown.

## SDH behavior

Examples:

```text
[door]

Where are you?
```

When an active-speaker/vision adapter has established that an identified character is speaking off-screen:

```text
Carrie: Where are you?
```

Music is treated separately:

```text
♪ musique ♪
```

The pipeline intentionally does not label every visible line with a character name. Debug metadata can be rich; the subtitle should stay readable.

## Fast video text strategy

Full OCR on every frame is explicitly rejected.

Preferred gate:
- Intel/OpenVINO `horizontal-text-detection-0001`
- real-time demo: https://docs.openvino.ai/2024/openvino-workflow/model-server/ovms_demo_horizontal_text_detection.html

The detector only decides **where text exists**. Recognition then runs on new or changed text crops only. Stable crops are tracked and cached across frames.

For rotated or difficult text, a heavier detector is only used as a fallback on selected frames/crops.

See `docs/PERFORMANCE_REFERENCES.md` for the benchmark numbers and links.

## Agent-friendly repository

- `AGENTS.md` contains stable coding rules.
- `skills/repo-navigation/SKILL.md` routes Codex/Pi by task.
- `docs/PIPELINE_RUNTIME.md` describes provider boundaries and handoff.
- `docs/PERFORMANCE_REFERENCES.md` documents performance evidence and optimization choices.
- heavy ML imports are lazy.
- pure orchestration helpers have unit tests.

## Important design rules

- raw ASR is always preserved
- uncertain text is corrected only with strong evidence
- character identity and visual visibility are separate evidence
- character names must be story-safe
- only plot-relevant sound events should reach visible subtitles
- expensive video/audio models should be gated by cheap detectors whenever possible

## Next extensions

1. OpenVINO sparse text detector + text-track cache + recognizer adapter
2. Active-speaker detection, benchmarking LR-ASD before TalkNet
3. Tiny sound-event scout before heavier PANNs verification
