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
│  ├─ scoring.yaml
│  └─ style_rules.yaml
├─ docs/
│  └─ SDH_STYLE_GUIDE.md
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

## SDH policy

This project now includes:

- `docs/SDH_STYLE_GUIDE.md` for speaker IDs, sound effects, narration, and spoiler-safe naming
- `config/style_rules.yaml` for project-level SDH behavior

Highlights:

- show speaker labels only when needed for clarity
- prefer character names over actor names in visible subtitles
- do not reveal unrevealed names too early
- include only plot-pertinent or tonally relevant sound labels
- preserve raw ASR text and corrected text separately

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

- wire `style_rules.yaml` into runtime rendering
- add models and scoring refinements
- add IMDb TSV loader improvements
- add fusion engine refinements
- add exporters improvements
- add non-stub providers and end-to-end tests
