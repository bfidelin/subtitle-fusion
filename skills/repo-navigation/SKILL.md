# Repo navigation skill

## Purpose
Help a coding agent enter this repository quickly and make safe changes.

## Goal of the repository
The project builds enriched subtitles from video using:
- ASR output and uncertainty markers
- OCR from frames
- IMDb title and character context
- SDH style rules
- optional audio-event, music, track-recognition, and lyric-assistance hooks

## Fast entry sequence
1. Read `AGENTS.md`
2. Read `docs/REPO_MAP.md`
3. Read `README.md`
4. Read the relevant policy doc:
   - `docs/SDH_STYLE_GUIDE.md`
   - `docs/AUDIO_EVENTS_AND_MUSIC.md`
5. Read the relevant config file under `config/`
6. Read the code file you plan to modify
7. Read the matching test file under `tests/`

## If the task is about...
### Subtitle text correction
Read:
- `src/models.py`
- `src/scoring.py`
- `src/fusion.py`
- `tests/test_scoring.py`
- `tests/test_fusion.py`
- `tests/test_uncertain_words.py`

### Speaker labels or SDH output
Read:
- `docs/SDH_STYLE_GUIDE.md`
- `config/style_rules.yaml`
- `src/exporters.py`

### IMDb or character disambiguation
Read:
- `src/imdb_index.py`
- `src/fusion.py`
- `docs/SDH_STYLE_GUIDE.md`

### Audio events, music, or lyrics
Read:
- `docs/AUDIO_EVENTS_AND_MUSIC.md`
- `config/audio_analysis.yaml`
- `src/audio_music.py`
- `src/track_recognition.py`
- `src/pipeline.py`

## Stable rules
- Do not overwrite `text_raw`.
- Use `decision` and `text_corrected` for corrections.
- Prefer small, local changes.
- Add or update tests with behavior changes.
- Keep visible subtitle output concise.
- Prefer metadata/debug JSON for rich evidence.
- Do not reveal character names before the story reveals them.

## Output expectations
When changing logic, keep these outputs coherent:
- `output.debug.json`
- `output.srt`
- `output.ass`

## Validation
Use:
```bash
pip install -e .[dev]
pytest -q
```

## Smoke test
```bash
subtitle-fusion run \
  --video /tmp/fake-video.mkv \
  --title "Example Show" \
  --season 1 \
  --episode 3 \
  --imdb-title-id tt1234567 \
  --output-dir /tmp/subtitle-fusion-out
```

## What good changes look like
- add one small capability
- update docs/config if behavior changes
- keep the repo navigable for the next agent
