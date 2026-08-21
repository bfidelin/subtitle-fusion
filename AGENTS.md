# AGENTS.md

This repository is configured to be easy for coding agents to navigate.

## Goal
Build a Python project that produces enriched subtitles from video by combining:
- primary ASR with timestamps and uncertainty markers
- very-fast scout ASR/OCR/audio analysis to locate difficult regions
- first-class speaker diarization with stable episode-local speaker IDs and overlap detection
- speaker-to-character identity resolution kept separate from diarization
- selective local re-ASR/review instead of expensive whole-episode reprocessing
- OCR from frames
- IMDb/show context for characters and titles
- SDH rendering rules
- optional audio-event, music, singing, lyric and track-recognition hooks
- Netflix-style French timed-text validation

## Keep this file minimal
Only put stable, high-value instructions here.
Do not duplicate detailed design docs.

## First files to read
1. `README.md`
2. `docs/FAST_SCOUT_PIPELINE.md`
3. `docs/SDH_STYLE_GUIDE.md`
4. `docs/NETFLIX_FR_STYLE.md`
5. `docs/AUDIO_EVENTS_AND_MUSIC.md`
6. `config/scoring.yaml`
7. `config/style_rules.yaml`
8. `config/audio_analysis.yaml`
9. `src/models.py`
10. `src/pipeline.py`
11. `src/fusion.py`
12. `src/scoring.py`

## Repository map
- `src/models.py`: core data classes for segments, words, decisions, speaker IDs, and pipeline results
- `src/scoring.py`: confidence thresholds and uncertain-word marking
- `src/fusion.py`: candidate scoring and correction decisions
- `src/imdb_index.py`: local IMDb TSV loading and candidate extraction
- `src/audio_music.py`: audio event and music analysis interfaces
- `src/track_recognition.py`: ranking of track candidates using multiple signals
- `src/netflix_style.py`: Netflix-style French layout/timing validation
- `src/exporters.py`: JSON, SRT, and ASS output
- `src/pipeline.py`: orchestration and future integration points
- `docs/FAST_SCOUT_PIPELINE.md`: fast scouts, diarization, evidence timeline, confidence router, selective escalation and backend strategy
- `docs/SDH_STYLE_GUIDE.md`: diarization-aware speaker rendering and SDH policy
- `docs/`: style and architecture guidance
- `config/`: runtime policy and thresholds
- `tests/`: unit tests

## Working rules
- Preserve `text_raw`; never overwrite it.
- Put corrections in `text_corrected` and `decision`.
- Only auto-correct uncertain content when evidence is strong.
- Confidence controls compute cost: expensive processing should be selective and local.
- Prefer cheap whole-episode scouts over expensive whole-episode second passes.
- Treat diarization as a first-class timestamped evidence stream.
- Keep `speaker_id` separate from character identity. `SPEAKER_03` does not mean `Muriel` until independent evidence resolves it.
- Preserve overlap information instead of forcing all speech into one speaker.
- Keep ASR/OCR/diarization/audio/source-separation providers behind replaceable adapters.
- Prefer character names over actor names in visible subtitle text.
- Do not reveal names before the story reveals them.
- Keep visible SDH output concise.
- Store rich evidence in debug JSON rather than in visible subtitles.
- The Netflix formatter may change layout/timing safely but must never invent, truncate or paraphrase dialogue silently.

## Evidence priority
Use this order when resolving uncertain names/tokens:
1. OCR explicit on-screen text
2. IMDb character match restricted to current title/episode
3. names already validated in show/episode glossary
4. dialogue context
5. validated speaker-to-character continuity
6. actor/face hint
7. phonetic similarity

A disagreement between a cheap scout ASR and the primary ASR is an escalation signal, not an automatic correction.
A high diarization confidence is not enough to assign a character name.

## Diarization policy
- Produce stable episode-local speaker IDs where possible.
- Preserve speaker-turn boundaries and overlap regions.
- Add a diarization confidence/quality signal when the backend exposes one.
- Use fast whole-episode speaker-change/embedding analysis first.
- Escalate only ambiguous boundaries, overlaps or speaker-identity conflicts.
- Let ASR consume diarization boundaries when useful, but keep ASR and diarization independently inspectable.
- Resolve character identity in a separate layer using OCR/context/IMDb/validated mappings/optional visual hints.
- Speaker labels in final SDH output are a rendering decision; they are not simply a dump of `speaker_id`.

## Confidence policy
Keep evidence dimensions explainable where practical rather than collapsing them into one opaque score:
- ASR confidence
- scout agreement
- diarization confidence
- speaker identity confidence
- OCR confidence
- proper-name confidence
- context confidence
- translation confidence
- linguistic QA confidence
- final routing/decision confidence

## Audio and music policy
- Treat sound-event detection, music detection, singing detection, track recognition, source separation and lyric transcription as separate tasks.
- Run cheap event/music scouts over the episode.
- Run Demucs/source separation only on selected windows where it can improve lyrics/dialogue.
- Use lyrics and musical signals to rerank track candidates, not as a blind replacement for recognition.
- Keep commercial track identification mostly in metadata by default.

## Test commands
```bash
pip install -e .[dev]
pytest -q
```

## Local smoke test
```bash
subtitle-fusion run \
  --video /tmp/fake-video.mkv \
  --title "Example Show" \
  --season 1 \
  --episode 3 \
  --imdb-title-id tt1234567 \
  --output-dir /tmp/subtitle-fusion-out
```

## Preferred implementation order
1. ingest real Faster-Whisper word/timestamp/confidence data
2. add evidence timeline + confidence router
3. add first-class diarization turns, overlaps and stable speaker IDs
4. add local audio crop + selective re-ASR
5. wire fast OCR detection/region recognition
6. add show/episode proper-name glossary persistence
7. add speaker-identity resolution separate from diarization
8. add Moonshine-style scout ASR adapter
9. add audio-event/music/singing routing
10. add selective Demucs + vocal ASR
11. add translation + grammar/spelling/context reviewer
12. add shot-aware Netflix timing
13. profile and calibrate thresholds on real episodes

## Avoid
- large speculative rewrites
- expensive whole-episode processing when a local window is sufficient
- conflating diarization with character identification
- discarding overlapping-speaker evidence
- coupling core semantics to one hardware/backend provider
- changing output semantics without updating docs and tests
- adding long, stale instructions to this file
