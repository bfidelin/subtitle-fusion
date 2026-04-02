# subtitle-fusion

Production-oriented Python project to generate enriched subtitles from video by combining:

- ASR with word timestamps and confidence
- speaker diarization
- OCR from video frames
- IMDb context for title, cast, and character names
- optional actor/face hints
- rule-based fusion and SDH output

## Planned outputs

- `output.debug.json`
- `output.srt`
- `output.ass`

## Initial layout

```text
subtitle_fusion/
├─ pyproject.toml
├─ README.md
├─ .env.example
├─ config/
│  ├─ settings.yaml
│  └─ scoring.yaml
├─ src/
│  ├─ main.py
│  ├─ pipeline.py
│  ├─ models.py
│  ├─ scoring.py
│  ├─ imdb_index.py
│  ├─ fusion.py
│  └─ exporters.py
└─ tests/
   ├─ test_scoring.py
   ├─ test_fusion.py
   └─ test_imdb_index.py
```

## Core design

The pipeline should only auto-correct uncertain segments, using evidence in this order:

1. explicit OCR text on screen
2. IMDb candidates restricted to the current title/episode
3. dialogue context
4. actor/face hint
5. phonetic similarity

Raw ASR text must always be preserved alongside corrected text.

## Example CLI

```bash
subtitle-fusion run \
  --video /path/video.mkv \
  --title "Example Show" \
  --season 1 \
  --episode 3 \
  --imdb-title-id tt1234567 \
  --output-dir ./out
```

## Next steps

- add models and scoring
- add IMDb TSV loader
- add fusion engine
- add exporters
- add stub pipeline + tests
