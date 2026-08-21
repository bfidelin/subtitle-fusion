# AGENTS.md

This repository is configured for Codex, Pi and other coding agents.

## Goal
Build a fast enriched-subtitle pipeline combining WhisperX/pyannote, reuse of existing subtitle evidence, sparse OCR/audio/vision analysis, conservative character identity, professional SDH formatting and reproducible QC.

## Read first
1. `README.md`
2. `docs/STANDARDS_AND_PRACTICES.md`
3. `docs/PERFORMANCE_TARGETS.md`
4. `docs/OPTIMIZATION_PLAYBOOK.md`
5. `docs/FAST_SCOUT_PIPELINE.md`
6. `docs/WHISPERX_PYANNOTE_RUNTIME.md`
7. `docs/NETFLIX_FR_STYLE.md`
8. `docs/SDH_STYLE_GUIDE.md`
9. `docs/PERFORMANCE_REFERENCES.md` when making performance/model claims
10. relevant code/config/tests

## Runtime baseline
`WhisperXProvider` supplies whole-episode Faster-Whisper ASR, forced word alignment and pyannote Community-1 diarization/embeddings/overlap evidence.

Do **not** add a duplicate whole-episode Faster-Whisper pass. Extra ASR must be selective/local unless measured evidence proves otherwise.

Before expensive analysis, prefer media preflight and existing-track reuse. `src/media_preflight.py` inventories text/image subtitle tracks and audio streams using ffprobe.

## Non-negotiable rules
- Preserve `text_raw`; never overwrite raw evidence.
- Semantic edits must be traceable; formatters may not invent or silently paraphrase dialogue.
- Unknown speaker/character is better than a false identity.
- `speaker_id`, character identity and visual visibility are separate evidence.
- Failed face detection is not proof of off-screen speech.
- Preserve overlapping-speaker evidence.
- Do not reveal names before the story establishes them.
- Visible SDH stays concise; rich evidence belongs in debug output.
- Expensive models are gated by cheap scouts/quality checks.
- Heavy ML imports stay lazy so core tests run without GPU packages.
- Model/provider changes require fake/small-data tests.
- Local measured performance overrides external projections.

## Professional timing/layout
Follow `docs/STANDARDS_AND_PRACTICES.md` and the active output profile. For Netflix-style fr-FR in particular, preserve:
- max 42 visible chars/line
- max 2 lines
- 20-frame minimum and 7 s maximum duration
- 2-frame minimum gap
- shot-aware timing, not audio-only timing
- clause-aware/bottom-heavy line breaks
- CPS and WPM QC

Never shorten meaning automatically merely to satisfy a reading-speed metric.

## Optimization policy
Preferred order:
1. inspect/reuse embedded text subtitle tracks
2. OCR PGS/image subtitle events before arbitrary full-frame OCR
3. reuse shared audio/VAD/shot maps and caches
4. cheap global sync/quality preflight
5. cheap scouts
6. batch/local verifiers only on candidates
7. deterministic QC/rendering

Video OCR default:
```text
scene cuts + ~0.5 fps
 -> mobile/tiny text detector
 -> track boxes + perceptual hash
 -> OCR new/changed crops only
 -> temporal voting
```

Active speaker: speech windows only, reuse face tracks, benchmark LR-ASD before TalkNet.

Audio: cheap AudioSet/YAMNet-class scout -> PANNs verifier -> Demucs only on selected vocal-music windows.

## Character voiceprints
Use `src/voiceprints.py` with both:
- minimum absolute similarity
- minimum margin over the second-best identity

Keep bounded enrollment history and leave weak matches unknown.

## Validation
```bash
pip install -e '.[dev]'
ruff check .
pytest -q
```

WhisperX smoke runtime:
```bash
pip install -e '.[whisperx,dev]'
export HF_TOKEN=hf_...
```

Audio verifier runtime:
```bash
pip install -e '.[audio]'
```

## Definition of done
- tests/lint pass
- docs/config semantics updated
- no eager heavy-model import
- raw/debug evidence preserved
- no uncited performance claim
- performance-sensitive work records local benchmark data when runtime hardware is available
- standard/profile claims distinguish implemented checks from planned/unsupported compliance
