# subtitle-fusion

Production-oriented Python project to generate enriched subtitles from video by combining:

- ASR with word timestamps and confidence
- speaker diarization
- OCR from video frames
- IMDb context for title, cast, and character names
- optional actor/face hints
- rule-based fusion and SDH output
- audio-event, music, and track-recognition hooks
- Netflix-style French (France) formatting and compliance checks

## Planned outputs

- `output.debug.json`
- `output.srt`
- `output.ass`
- `output.netflix-report.json`

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
│  ├─ NETFLIX_FR_STYLE.md
│  └─ AUDIO_EVENTS_AND_MUSIC.md
├─ src/
│  ├─ main.py
│  ├─ pipeline.py
│  ├─ models.py
│  ├─ scoring.py
│  ├─ imdb_index.py
│  ├─ fusion.py
│  ├─ netflix_style.py
│  ├─ exporters.py
│  ├─ audio_music.py
│  └─ track_recognition.py
└─ tests/
   ├─ test_scoring.py
   ├─ test_fusion.py
   ├─ test_imdb_index.py
   └─ test_netflix_style.py
```

## Core design

The pipeline should only auto-correct uncertain segments, using evidence in this order:

1. explicit OCR text on screen
2. IMDb candidates restricted to the current title/episode
3. dialogue context
4. actor/face hint
5. phonetic similarity

Raw ASR text must always be preserved alongside corrected text.

## Netflix-style French output

`src/netflix_style.py` and the `netflix` section of `config/style_rules.yaml` apply a French (France) timed-text profile before export.

Current checks/formatting include:

- 42 visible characters maximum per line
- 2 lines maximum
- syntactic/bottom-heavy line breaking when possible
- 5/6 second minimum duration and 7 second maximum
- 17 CPS preferred target and 20 CPS French SDH ceiling
- 2-frame minimum inter-subtitle gap
- chaining of short gaps below half a second when safe
- no silent truncation or paraphrasing to satisfy layout limits
- a machine-readable `output.netflix-report.json` for remaining violations

See `docs/NETFLIX_FR_STYLE.md` for the official Netflix references and the distinction between Netflix-style compliance and an official Netflix delivery package.

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
- use French bracketed/lowercase generic SDH labels

## Confidence and proper-name review

The existing scoring layer marks low-confidence ASR words and proper-noun candidates for contextual review. The fusion layer can combine OCR matches with title-scoped IMDb character/actor candidates before auto-correcting. This is intentionally conservative.

Still to be wired end-to-end:

- real OCR extraction from video frames (the OCR data model and fusion hooks already exist)
- translation confidence distinct from ASR confidence
- grammar, spelling and punctuation proofreading
- context-aware linguistic rewriting without semantic drift
- episode/show glossary and continuity checks for recurring proper names
- a second-pass reviewer that can reject unsafe translation/correction suggestions

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

- replace stub segments with real ASR/diarization input
- wire real OCR frame extraction and title/name harvesting
- add translation + linguistic QA confidence and second-pass review
- add shot-change-aware Netflix timing
- wire `audio_analysis.yaml` into audio/music providers
- add non-stub providers and end-to-end tests
