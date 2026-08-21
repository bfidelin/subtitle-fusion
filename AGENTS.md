# AGENTS.md

This repository is configured to be easy for coding agents to navigate.

## Goal
Build a fast enriched-subtitle pipeline combining:
- WhisperX/Faster-Whisper ASR with word alignment/confidence
- pyannote speaker diarization
- cheap scout ASR/OCR/audio analysis
- selective local re-ASR/review
- OCR + IMDb/show context for proper names
- speaker-to-character identity resolution
- SDH audio/music/lyrics enrichment
- Netflix-style French timed-text validation

## First files to read
1. `README.md`
2. `docs/FAST_SCOUT_PIPELINE.md`
3. `docs/WHISPERX_PYANNOTE_RUNTIME.md`
4. `docs/SDH_STYLE_GUIDE.md`
5. `docs/NETFLIX_FR_STYLE.md`
6. `docs/AUDIO_EVENTS_AND_MUSIC.md`
7. `config/settings.yaml`
8. `config/scoring.yaml`
9. `src/models.py`
10. `src/whisperx_provider.py`
11. `src/pipeline.py`
12. `src/fusion.py`

## Current runtime baseline
The real whole-episode baseline is now `WhisperXProvider`:
- WhisperX batched Faster-Whisper ASR
- forced word alignment
- pyannote `speaker-diarization-community-1`
- word/segment speaker IDs
- speaker turns and embeddings
- overlap evidence

Do **not** add a second whole-episode Faster-Whisper pass before WhisperX. WhisperX already uses Faster-Whisper internally. Future extra ASR work must be selective/local unless benchmarking proves otherwise.

WhisperX is an optional heavy dependency. Core/unit tests must remain runnable without loading GPU models.

## Working rules
- Preserve `text_raw`; never overwrite it.
- Put corrections in `text_corrected` and `decision`.
- Only auto-correct uncertain content when evidence is strong.
- Confidence controls compute cost.
- Keep `speaker_id` separate from character identity.
- Preserve overlap information instead of flattening speakers.
- Keep providers behind replaceable adapters.
- Prefer character names over actor names in visible subtitles.
- Never reveal names before the story reveals them.
- Store rich evidence in debug JSON, not visible subtitles.
- Netflix formatting may change safe layout/timing but must not invent/truncate/paraphrase dialogue silently.

## Evidence priority for uncertain names/tokens
1. explicit on-screen OCR
2. title/episode-restricted character candidates
3. names already validated in show/episode glossary
4. dialogue context
5. validated speaker-to-character continuity
6. actor/face hint
7. phonetic similarity

Scout disagreement or high diarization confidence is evidence, not an automatic correction.

## Confidence dimensions
Keep independent signals where practical:
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

## Audio/music policy
- Treat sound events, music, singing, track recognition, source separation and lyric transcription separately.
- Run cheap scouts broadly.
- Run Demucs/source separation only on selected windows.

## Install / tests
Core tests:
```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

WhisperX runtime:
```bash
pip install -e ".[whisperx,dev]"
export HF_TOKEN=hf_...
```

The Hugging Face account must have accepted the `pyannote/speaker-diarization-community-1` model conditions.

## Preferred implementation order
WhisperX ingestion + first-class pyannote diarization are now baseline-complete. Next:
1. timestamped evidence timeline + confidence router
2. local audio crop + selective re-ASR
3. fast OCR detection/region recognition
4. persistent show/episode proper-name glossary
5. speaker-to-character identity resolver
6. Moonshine-style independent scout ASR
7. audio-event/music/singing routing
8. selective Demucs + vocal ASR
9. translation + grammar/spelling/context reviewer
10. shot-aware Netflix timing
11. real-episode profiling and threshold calibration

## Avoid
- expensive duplicate whole-episode ASR passes
- conflating diarization with character identity
- discarding overlap evidence
- coupling core semantics to one backend/hardware provider
- changing output semantics without docs/tests
