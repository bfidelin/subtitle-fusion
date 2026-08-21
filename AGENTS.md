# AGENTS.md

This repository is configured for Codex, Pi and other coding agents.

## Goal
Build a fast enriched-subtitle pipeline combining WhisperX/pyannote, reuse of existing subtitle evidence, sparse OCR/audio/vision analysis, conservative character identity, professional SDH formatting and reproducible QC.

## Read first
1. `README.md`
2. `docs/STANDARDS_AND_PRACTICES.md`
3. `docs/TRANSLATOR_QC_CHECKLIST.md`
4. `docs/PERFORMANCE_TARGETS.md`
5. `docs/OPTIMIZATION_PLAYBOOK.md`
6. `docs/FAST_SCOUT_PIPELINE.md`
7. `docs/WHISPERX_PYANNOTE_RUNTIME.md`
8. `docs/NETFLIX_FR_STYLE.md`
9. `docs/SDH_STYLE_GUIDE.md`
10. `docs/PERFORMANCE_REFERENCES.md` when making performance/model claims
11. relevant code/config/tests

## Runtime baseline
`WhisperXProvider` supplies whole-episode Faster-Whisper ASR, forced word alignment and pyannote Community-1 diarization/embeddings/overlap evidence.

Do **not** add a duplicate whole-episode Faster-Whisper pass. Extra ASR must be selective/local unless measured evidence proves otherwise.

`src/media_preflight.py` already inventories text/image subtitle tracks and audio streams using ffprobe. **Do not implement another inventory scanner.** The missing capability is quality-gated extraction/source selection and synchronization repair.

## Source/reference selection policy
A found subtitle track is evidence, not automatically truth.

Before replacing WhisperX with an existing track, score at least:
- language match
- coverage/completeness
- timestamp monotonicity/overlap sanity
- VAD/audio synchronization fit
- sampled lexical/ASR agreement
- likely edit/version mismatch
- whether the track is dialogue-only vs SDH/CC

Preferred routing:
```text
good text + good sync -> reuse/enrich
good text + global offset/drift -> repair -> reuse/enrich
piecewise mismatch -> piecewise alignment
bad/incomplete/wrong-language -> WhisperX, track remains secondary evidence
```

PGS/image subtitle streams should be processed at subtitle-event/bitmap level before arbitrary full-frame OCR.

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
- Keep ASR, source-track quality, sync, OCR, identity, translation and linguistic-QA confidence independently inspectable.
- **SRT is the primary playback output.**
- **IMSC/TTML is inactive. Do not add an exporter, dependency, config path or roadmap item unless the user explicitly re-enables it.**

## Translation / proofreading policy
Follow `docs/TRANSLATOR_QC_CHECKLIST.md`.

Do not use one opaque LLM pass for translation + grammar + timing + line breaking. Keep stages explicit:
```text
source/template -> glossary -> translation -> semantic review
 -> grammar/spelling -> subtitle adaptation -> SDH/FN -> timing/QC
```

For uncertain proper names, prefer explicit OCR/trusted template/title-scoped metadata/validated glossary over phonetic similarity. Never allow fluent rewriting to change reveal order, register, jokes, ambiguity or character voice silently.

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

### SRT placement
Dynamic placement should stay in the SRT path rather than requiring a second master format.

Target behavior:
```text
bottom-center by default
 -> plot-relevant lower-screen OCR collision
 -> top-center on supported Jellyfin profile (`{\an8}`)
 -> keep placement stable through the shot/sequence
```

Rules:
- reuse OCR boxes and shot-map evidence
- do not run a separate detector only for layout
- placement tags are compatibility extensions, not universal SRT standard features
- retain placement reason/confidence/avoid boxes in debug data
- a player ignoring placement tags must still receive valid readable dialogue text
- avoid top/bottom ping-pong between consecutive cues

This placement engine is planned, not implemented yet.

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

## Shared evidence rule
Compute expensive media-derived structure once and reuse it.

A single cached shot map should serve:
- subtitle timing
- OCR sampling
- face/ASD track refresh
- structural discontinuity/recap detection
- subtitle placement stability/reset

A shared audio/VAD derivative should serve synchronization and routing where compatible. Cache keys must include media fingerprint and relevant model/config versions.

## Character voiceprints
Use `src/voiceprints.py` with both:
- minimum absolute similarity
- minimum margin over the second-best identity

Keep bounded enrollment history and leave weak matches unknown.

## Season/batch workers
For season/library processing:
- load heavy models once and keep them warm
- reuse show glossary and voiceprint centroids
- bound GPU concurrency to avoid VRAM thrash
- do not reload WhisperX/pyannote/OCR/audio models for every episode
- prefetch/decode the next episode only when it does not slow the bottleneck stage

## Output policy
Current outputs are SRT, optional ASS, debug JSON and the Netflix compliance report when enabled.

SRT is the primary playback target. IMSC/TTML is deliberately inactive and should remain reference-only documentation unless explicitly re-enabled.

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
- source/reference selection and semantic edits are traceable
- SRT remains a valid primary output
- no inactive IMSC/TTML runtime path is introduced
- no uncited performance claim
- performance-sensitive work records local benchmark data when runtime hardware is available
- standard/profile claims distinguish implemented checks from planned/unsupported compliance
