# Repository map

This is the short orientation guide. Detailed rules live in `AGENTS.md` and the referenced docs.

## Read in this order
1. `AGENTS.md`
2. `README.md`
3. `docs/STANDARDS_AND_PRACTICES.md`
4. `docs/PERFORMANCE_TARGETS.md`
5. `docs/OPTIMIZATION_PLAYBOOK.md`
6. `docs/FAST_SCOUT_PIPELINE.md`
7. `docs/WHISPERX_PYANNOTE_RUNTIME.md`
8. relevant provider/config/tests

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

## Key configs
- `config/settings.yaml`: runtime/preflight/OCR/voiceprint/cache policy
- `config/scoring.yaml`: correction thresholds
- `config/style_rules.yaml`: Netflix/SDH formatting profile
- `config/audio_analysis.yaml`: scout -> verifier audio/music policy

## Key docs
- `docs/STANDARDS_AND_PRACTICES.md`: professional timed-text/translation/SDH rules
- `docs/PERFORMANCE_REFERENCES.md`: benchmark sources and useful videos
- `docs/PERFORMANCE_TARGETS.md`: performance decisions and benchmark contract
- `docs/OPTIMIZATION_PLAYBOOK.md`: prior art from ffsubsync, Alass, Subtitle Edit, stable-ts
- `docs/NETFLIX_FR_STYLE.md`: Netflix-style fr-FR profile details
- `docs/SDH_STYLE_GUIDE.md`: speaker/sound rendering rules
- `docs/AUDIO_EVENTS_AND_MUSIC.md`: music/event/lyrics architecture

## Important architecture boundaries
- WhisperX is the global ASR baseline; do not add a redundant full Faster-Whisper pass.
- Diarization speaker IDs are not character identities.
- Character identity is not visual visibility.
- Shot boundaries should become shared cached evidence for timing, OCR and ASD.
- Existing subtitle tracks should be scored/reused before expensive regeneration.
- Full OCR on every video frame and full-episode Demucs are forbidden default paths.

## Highest-value next steps
1. wire media preflight to extraction/reference selection with quality gates
2. shared cached shot map
3. VAD/FFT-style global sync preflight and piecewise fallback
4. deterministic post-ASR segmentation/QC with CPS + WPM + shot-aware timing
5. sparse Paddle text detection/tracking/crop OCR
6. finish voiceprint enrollment UX/identity continuity
7. YAMNet-class audio scout -> PANNs verifier
8. sparse LR-ASD active-speaker provider
9. IMSC 1.3 exporter + validator
10. benchmark harness + warm season worker
