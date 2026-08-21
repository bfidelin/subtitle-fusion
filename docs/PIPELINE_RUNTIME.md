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
  -> IMDb/text fusion
  -> SDH renderer
  -> output.debug.json + output.srt + output.ass
```

Heavy ML dependencies are optional extras and are imported lazily. This keeps `pytest`, `ruff`, Codex and Pi usable on a laptop or CI runner without CUDA.

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

The active-speaker/vision provider is intentionally a separate extension point. Until TalkNet or another active-speaker detector is connected, `speaker_visible` remains unknown and names stay in debug metadata rather than being spammed on-screen.

This is deliberate: voice identity and visual visibility are different evidence.

## Audio events

PANNs runs on short overlapping windows. Only labels in `config/audio_analysis.yaml:audio_events.labels_allowlist` are emitted.

`Music` is kept separate from generic effects and becomes `MusicInfo.present`. Avoid dumping every AudioSet label into subtitles.

## Codex / Pi work protocol

1. Read `AGENTS.md`.
2. Read this file and `docs/SDH_STYLE_GUIDE.md`.
3. Prefer provider adapters over changes to orchestration.
4. Keep heavy imports inside provider methods.
5. Add a fake-provider unit test for every orchestration change.
6. Preserve `text_raw`.
7. Do not make a speaker identity visible unless evidence is strong and story-safe.
8. Run `pytest -q` and `ruff check .` before proposing a merge.

## Next safe extensions

- active-speaker provider (TalkNet or equivalent) that sets `Segment.speaker_visible`
- OCR provider wiring
- music mood classifier
- Demucs + lyric transcription
- pluggable commercial track recognition
- batching/cache reuse across Sonarr/Jellyfin libraries
