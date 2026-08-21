# Repo navigation skill

## Purpose
Help Codex, Pi, or another coding agent make safe changes quickly.

## Fast entry
1. `AGENTS.md`
2. `docs/PIPELINE_RUNTIME.md`
3. `README.md`
4. the relevant policy/config
5. implementation + matching tests

## Task routes

### ASR / timestamps
Read:
- `src/asr.py`
- `src/media.py`
- `src/models.py`
- `config/settings.yaml`

Keep WhisperX imports lazy. ASR must not own speaker identity.

### Diarization / speaker assignment
Read:
- `src/diarization.py`
- `src/voiceprints.py`
- `tests/test_diarization.py`
- `tests/test_voiceprints.py`

Community-1 returns speaker embeddings. Preserve raw `SPEAKER_*` IDs in debug data.

### Character names / voiceprints
Read:
- `src/voiceprints.py`
- `docs/PIPELINE_RUNTIME.md`
- `config/settings.yaml`

Never force a match below both score and margin thresholds.

### SDH / off-screen labels
Read:
- `src/exporters.py`
- `config/style_rules.yaml`
- `docs/SDH_STYLE_GUIDE.md`
- `tests/test_exporters_sdh.py`

Voice identity is not visibility. Only an active-speaker/vision provider may set `speaker_visible`.

### Audio events / music
Read:
- `src/audio_music.py`
- `config/audio_analysis.yaml`
- `docs/AUDIO_EVENTS_AND_MUSIC.md`

Prefer a small allowlist and merge repeated windows.

### Text correction
Read:
- `src/scoring.py`
- `src/fusion.py`
- `src/imdb_index.py`
- matching tests

Never overwrite `text_raw`.

## Validation
```bash
pip install -e '.[dev]'
pytest -q
ruff check .
```

For model-level smoke tests:
```bash
pip install -e '.[runtime]'
export HUGGINGFACE_TOKEN=...
```

## Definition of done
- behavior covered by tests
- configs/docs updated with semantics
- no eager heavy-model import
- debug JSON preserves evidence
- SRT/ASS remain concise
