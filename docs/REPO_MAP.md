# Repository map

This is the short orientation guide. Detailed rules live in `AGENTS.md` and the referenced docs.

## Read in this order
1. `AGENTS.md`
2. `README.md`
3. `docs/STANDARDS_AND_PRACTICES.md`
4. `docs/TRANSLATOR_QC_CHECKLIST.md`
5. `docs/PERFORMANCE_TARGETS.md`
6. `docs/OPTIMIZATION_PLAYBOOK.md`
7. `docs/FAST_SCOUT_PIPELINE.md`
8. `docs/WHISPERX_PYANNOTE_RUNTIME.md`
9. relevant provider/config/tests

## Current implemented runtime

Whole-episode baseline:
- `src/whisperx_provider.py`: WhisperX/Faster-Whisper + alignment + pyannote Community-1
- `src/pipeline.py`: orchestration, media preflight, evidence fusion, Netflix profile/export
- `src/media_preflight.py`: ffprobe inventory of audio/text/image subtitle tracks
- `src/voiceprints.py`: conservative per-series speaker-embedding identity store
- `src/netflix_style.py`: fr-FR timed-text formatting/QC
- `src/exporters.py`: JSON/SRT/ASS

Optional/partial providers:
- `src/audio_music.py`: audio/music primitives plus optional PANNs verifier; cheap YAMNet scout still to be wired
- `src/track_recognition.py`: track-candidate ranking hooks

Evidence/correction:
- `src/models.py`: canonical data model
- `src/scoring.py`: uncertainty/review routing primitives
- `src/fusion.py`: conservative correction decisions
- `src/imdb_index.py`: title-scoped IMDb evidence

## Implemented vs planned

| Area | Status | Next step |
|---|---|---|
| WhisperX ASR/alignment | implemented | selective/local re-ASR only |
| pyannote diarization/embeddings | implemented | preserve/consume evidence downstream |
| media ffprobe inventory | implemented | quality-gated extraction/reference selection |
| Netflix-style fr-FR formatter | implemented | shared shot-map integration + broader QC |
| SRT export | implemented | collision-aware placement extensions |
| voiceprint store | implemented | enrollment/continuity UX |
| PANNs verifier adapter | partial/optional | cheap scout before verifier |
| existing subtitle reuse | planned | language/coverage/sync/lexical quality gate |
| global sync repair | planned | VAD/FFT-style fast preflight |
| alternate-edit alignment | planned | piecewise/split fallback |
| shot map | planned | compute/cache once; reuse timing/OCR/ASD/layout |
| sparse video OCR | planned | Paddle detector -> tracks/hash -> crop OCR |
| collision-aware SRT placement | planned | OCR/shot evidence -> stable `{\an8}`/bottom choice |
| active speaker | planned | sparse LR-ASD first |
| benchmark harness | planned | `output.benchmark.json` |
| warm season worker | planned | resident models + bounded GPU queue |
| IMSC/TTML | inactive/deferred | no runtime work unless explicitly re-enabled |

## Key configs
- `config/settings.yaml`: runtime/preflight/OCR/voiceprint/cache policy
- `config/scoring.yaml`: correction thresholds
- `config/style_rules.yaml`: Netflix/SDH formatting profile
- `config/audio_analysis.yaml`: scout -> verifier audio/music policy

## Key docs
- `docs/STANDARDS_AND_PRACTICES.md`: professional timed-text/translation/SDH/SRT-layout rules
- `docs/TRANSLATOR_QC_CHECKLIST.md`: practical translation, proofreading, proper-name, SDH and final-QC workflow
- `docs/PERFORMANCE_REFERENCES.md`: benchmark sources and useful videos
- `docs/PERFORMANCE_TARGETS.md`: performance decisions and benchmark contract
- `docs/OPTIMIZATION_PLAYBOOK.md`: prior art from ffsubsync, Alass, Subtitle Edit, stable-ts
- `docs/NETFLIX_FR_STYLE.md`: Netflix-style fr-FR profile details
- `docs/SDH_STYLE_GUIDE.md`: speaker/sound rendering rules
- `docs/AUDIO_EVENTS_AND_MUSIC.md`: music/event/lyrics architecture

## Important architecture boundaries
- WhisperX is the global ASR baseline; do not add a redundant full Faster-Whisper pass.
- Media preflight inventory already exists; do not build a second scanner.
- An embedded subtitle track is a candidate reference, not automatic truth.
- Diarization speaker IDs are not character identities.
- Character identity is not visual visibility.
- Shot boundaries should become shared cached evidence for timing, OCR, ASD and layout stability.
- Existing subtitle tracks should be scored/reused before expensive regeneration.
- Full OCR on every video frame and full-episode Demucs are forbidden default paths.
- Translation, semantic review, linguistic proofreading, subtitle adaptation and timing are separate stages.
- SRT is the primary playback output.
- IMSC/TTML is inactive and must not be added to runtime or roadmap without an explicit future decision.

## SRT placement target

```text
OCR/text boxes + shot map
        |
        +-> lower region free -> normal bottom placement
        |
        +-> important text collision -> top placement (`{\an8}` on supported Jellyfin profile)
        |
        `-> keep placement sticky through the shot/sequence
```

Positioning tags are a playback compatibility extension, not portable SRT standard behavior. Keep debug evidence and safe fallback semantics.

## Source/reference routing target

```text
media preflight
  -> candidate embedded subtitle
      -> quality + language + sync score
          -> good + synced: reuse/enrich
          -> good + global drift: repair/reuse
          -> alternate edit: piecewise align
          -> poor/incomplete: WhisperX baseline
```

For PGS/image subtitles, prefer subtitle-event bitmap OCR before scanning arbitrary video frames.

## Highest-value next steps
1. quality-gated extraction/reference selection using the existing media preflight
2. shared cached shot map
3. VAD/FFT-style global sync preflight and piecewise fallback
4. deterministic post-ASR segmentation/QC with CPS + WPM + shot-aware timing
5. sparse Paddle text detection/tracking/crop OCR
6. collision-aware SRT placement
7. finish voiceprint enrollment UX/identity continuity
8. YAMNet-class audio scout -> PANNs verifier
9. sparse LR-ASD active-speaker provider
10. benchmark harness + warm season worker
