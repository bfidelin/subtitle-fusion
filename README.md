# subtitle-fusion

Production-oriented Python project to generate enriched subtitles from video by combining:

- ASR with word timestamps and confidence
- speaker diarization
- OCR from video frames
- IMDb context for title, cast, and character names
- optional actor/face hints
- rule-based fusion and SDH output
- audio-event, music, and track-recognition hooks

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
│  ├─ style_rules.yaml
│  └─ audio_analysis.yaml
├─ docs/
│  ├─ SDH_STYLE_GUIDE.md
│  └─ AUDIO_EVENTS_AND_MUSIC.md
├─ src/
│  ├─ main.py
│  ├─ pipeline.py
│  ├─ models.py
│  ├─ scoring.py
│  ├─ imdb_index.py
│  ├─ fusion.py
│  ├─ exporters.py
│  ├─ audio_music.py
│  └─ track_recognition.py
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

## Audio and music policy

This project now also includes:

- `docs/AUDIO_EVENTS_AND_MUSIC.md` for event detection, music windows, track recognition, and lyrics policy
- `config/audio_analysis.yaml` for provider selection and thresholds
- `src/audio_music.py` for provider interfaces and stub data classes
- `src/track_recognition.py` for simple track-candidate scoring

Design direction:

- detect general sound events separately from dialogue ASR
- detect music windows separately from general sound events
- recognize commercial tracks through pluggable providers when configured
- use lyrics overlap and fingerprint-like evidence as candidate-ranking signals
- keep track-identification metadata separate from visible subtitle output by default

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
- wire `audio_analysis.yaml` into audio/music providers
- add models and scoring refinements
- add IMDb TSV loader improvements
- add fusion engine refinements
- add exporters improvements
- add non-stub providers and end-to-end tests
