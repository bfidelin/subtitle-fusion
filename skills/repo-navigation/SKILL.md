# Repo navigation skill

## Purpose
Help Codex, Pi or another coding agent make safe, performance-aware subtitle changes quickly.

## Fast entry
1. `AGENTS.md`
2. `docs/STANDARDS_AND_PRACTICES.md`
3. `docs/TRANSLATOR_QC_CHECKLIST.md`
4. `docs/PERFORMANCE_TARGETS.md`
5. `docs/OPTIMIZATION_PLAYBOOK.md`
6. `README.md`
7. relevant provider/config/tests

Use `docs/PERFORMANCE_REFERENCES.md` before making model-speed/device/sampling claims.

## Task routes

### ASR / timestamps
Read:
- `src/whisperx_provider.py`
- `src/models.py`
- `config/settings.yaml`
- `docs/WHISPERX_PYANNOTE_RUNTIME.md`

WhisperX already uses Faster-Whisper. Extra ASR must be selective/local unless measured otherwise.

### Media preflight / existing tracks
Read:
- `src/media_preflight.py`
- `docs/OPTIMIZATION_PLAYBOOK.md`
- `docs/TRANSLATOR_QC_CHECKLIST.md`
- `config/settings.yaml`

The ffprobe inventory already exists. Do not add a duplicate scanner. The next capability is quality-gated source selection/extraction.

Before trusting an embedded text track, evaluate language, coverage, timestamp sanity, VAD/audio sync, sampled lexical agreement and alternate-edit risk. Prefer PGS/event OCR before arbitrary whole-frame OCR.

### Diarization / speaker identity
Read:
- `src/whisperx_provider.py`
- `src/voiceprints.py`
- `src/models.py`
- `tests/test_voiceprints.py`

Keep acoustic speaker ID, character identity and visual visibility separate. Voiceprint matching requires score + second-best margin.

### Translation / proofreading / proper names
Read:
- `docs/TRANSLATOR_QC_CHECKLIST.md`
- `docs/STANDARDS_AND_PRACTICES.md`
- `src/scoring.py`
- `src/fusion.py`
- `src/imdb_index.py`

Keep translation, semantic review, grammar/spelling and subtitle adaptation separate. Preserve `text_raw`. Prefer explicit OCR/trusted template/title-scoped metadata/validated glossary over phonetic guessing for names.

### SDH / professional timing
Read:
- `docs/STANDARDS_AND_PRACTICES.md`
- `docs/TRANSLATOR_QC_CHECKLIST.md`
- `docs/NETFLIX_FR_STYLE.md`
- `docs/SDH_STYLE_GUIDE.md`
- `src/netflix_style.py`
- `src/exporters.py`
- `config/style_rules.yaml`

Shot timing is first-class. Formatters may make safe layout/timing changes but may not silently rewrite semantic content.

### Video text / OCR
Read:
- `docs/PERFORMANCE_TARGETS.md`
- `docs/PERFORMANCE_REFERENCES.md`
- `docs/OPTIMIZATION_PLAYBOOK.md`
- `config/settings.yaml`

Required architecture:
```text
shot cuts + sparse samples
 -> cheap text detector
 -> track boxes + perceptual hash
 -> OCR new/changed crops only
 -> temporal voting
```

Default detector candidates: PP-OCRv5 mobile, PP-OCRv6 tiny, OpenVINO horizontal specialist. Full OCR on every frame is not an acceptable default.

### Audio events / music / lyrics
Read:
- `src/audio_music.py`
- `config/audio_analysis.yaml`
- `docs/AUDIO_EVENTS_AND_MUSIC.md`
- `docs/OPTIMIZATION_PLAYBOOK.md`

Use cheap scout -> PANNs verifier. Demucs/source separation is selected vocal-music windows only.

### Active speaker / off-screen
Read:
- `src/models.py`
- `docs/PERFORMANCE_TARGETS.md`
- `docs/STANDARDS_AND_PRACTICES.md`

Benchmark LR-ASD before TalkNet. Analyze speech windows only, reuse face tracks and never infer off-screen from a failed face detector.

### Synchronization / alignment optimization
Read:
- `docs/OPTIMIZATION_PLAYBOOK.md`
- `docs/PERFORMANCE_TARGETS.md`
- `docs/TRANSLATOR_QC_CHECKLIST.md`

Try cheap global VAD/subtitle sync and quality scoring before expensive word-level repair. Escalate to piecewise alignment only for alternate edits/cuts/drift.

### Performance / profiling
Read:
- `docs/PERFORMANCE_TARGETS.md`
- `docs/PERFORMANCE_REFERENCES.md`
- `docs/OPTIMIZATION_PLAYBOOK.md`

Record cold/warm timing, RTF/FPS, pre/infer/post splits, RAM/VRAM, source-track quality, sync mode, cache hits and scout escalation rates. Local measurements override web projections.

### Season / batch processing
Read:
- `docs/PERFORMANCE_TARGETS.md`
- `docs/OPTIMIZATION_PLAYBOOK.md`

Keep heavy models resident across episodes, reuse show glossary/voiceprints, bound GPU concurrency and benchmark cold first-episode vs warm steady-state latency.

## Stable rules
- never overwrite raw evidence
- unknown is better than false identity/correction
- an embedded subtitle track is a candidate reference, not automatic truth
- provider imports stay lazy when heavy
- every behavior change gets tests
- visible SDH remains concise
- no performance/compliance claim without evidence
- semantic edits and safe mechanical fixes are different stages
- planned features must not be described as implemented

## Validation
```bash
pip install -e '.[dev]'
ruff check .
pytest -q
```

## Definition of done
- tests/lint pass
- configs/docs agree with behavior
- evidence stays inspectable in debug output
- source selection/semantic changes remain traceable
- heavy runtime remains optional
- performance-sensitive changes are benchmarkable
