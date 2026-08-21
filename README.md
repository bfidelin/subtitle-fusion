# subtitle-fusion

Production-oriented Python project for fast, enriched TV/movie subtitles. The project combines ASR, word timing/confidence, speaker diarization, OCR, title/show context, audio events/music, selective review and Netflix-style French SDH output.

The main rule is simple:

> **Do the cheap work on the whole episode; spend expensive compute only on uncertain windows.**

## Current runtime baseline

The first real media runtime is now implemented with **WhisperX + pyannote**:

- WhisperX batched Faster-Whisper ASR
- VAD-aware transcription
- forced word alignment
- word-level timestamps and alignment scores
- pyannote `speaker-diarization-community-1`
- stable episode-local `SPEAKER_xx` IDs
- speaker embeddings
- word/segment speaker assignment
- overlap evidence retained in the internal model

WhisperX is used as the baseline instead of running Faster-Whisper once and then retranscribing the whole episode with WhisperX a second time.

Detailed runtime notes: [`docs/WHISPERX_PYANNOTE_RUNTIME.md`](docs/WHISPERX_PYANNOTE_RUNTIME.md).

## Target architecture

```text
video/audio
   |
   +-> WhisperX ASR/alignment ----+
   +-> pyannote diarization ------+
   +-> tiny ASR scout ------------+
   +-> fast OCR detector ---------+-> timestamped evidence timeline
   +-> audio/music scout ---------+
   +-> shot detector -------------+
                                  |
                                  v
                         confidence router
                         /               \
                    accept            local review
                                         |
                   selective re-ASR + OCR + speaker
                    + names + local dialogue context
                                         |
                         grammar/translation QA
                                         |
                             Netflix / SDH output
```

The detailed design is in [`docs/FAST_SCOUT_PIPELINE.md`](docs/FAST_SCOUT_PIPELINE.md).

## Diarization is not character identification

Keep these concepts separate:

```text
speaker_id = SPEAKER_03
speaker_identity_candidate = Muriel
speaker_identity_confidence = 0.94
```

`SPEAKER_03` means pyannote believes these regions contain the same voice. Mapping that voice to `Muriel` is a later `subtitle-fusion` decision using OCR, visible context, IMDb/show metadata, previously validated mappings and other evidence.

A diarization cluster must never silently become a visible character name.

## Confidence-driven compute

Confidence is used to control cost, not only as a diagnostic field.

Initial routing direction, to calibrate on real episodes:

```text
> 0.90       accept unless another signal conflicts
0.70–0.90    lightweight context/name checks
0.45–0.70    selective local re-ASR + OCR/context
< 0.45       stronger local re-evaluation + reviewer
```

Other signals can escalate a segment even when the ASR score is high:

- scout ASR disagreement
- probable/unknown proper noun
- OCR conflict
- overlapping speakers
- uncertain speaker boundary or identity
- language switch
- music/singing contamination
- grammar/spelling anomaly
- inconsistent spelling of a previously validated name

Planned independent evidence fields include:

- `asr_confidence`
- `scout_agreement`
- `diarization_confidence`
- `speaker_identity_confidence`
- `ocr_confidence`
- `proper_noun_confidence`
- `context_confidence`
- `translation_confidence`
- `linguistic_qa_confidence`
- `final_confidence`

## Fast OCR and proper names

Do not OCR every frame at full quality. The intended flow is:

1. sample frames sparsely
2. run a cheap text detector
3. track stable regions
4. recognize only new/changed regions
5. escalate relevant or uncertain text to a stronger OCR model

High-value targets include character/name captions, location cards, phone/SMS text, signs and plot-relevant documents.

Provider direction: RapidOCR/ONNX Runtime or PP-OCR mobile for the fast path, with stronger OCR only where useful.

## Music, sounds and lyrics

Music is handled separately from normal dialogue ASR:

```text
music/singing detector
        |
        +--> instrumental -> concise SDH music label when relevant
        |
        +--> singing
                |
             local crop
                |
        Demucs only if useful
                |
          isolated vocals
                |
          lyric transcription
                |
         confidence/context
```

Do not run Demucs over the entire episode by default.

See [`docs/AUDIO_EVENTS_AND_MUSIC.md`](docs/AUDIO_EVENTS_AND_MUSIC.md).

## Netflix-style French / SDH

The project already contains a French Netflix-style formatter/validator and SDH policy.

Current checks include:

- maximum 42 visible characters per line
- maximum 2 lines
- syntactic/bottom-heavy line wrapping where possible
- minimum subtitle duration of 5/6 second
- maximum duration of 7 seconds
- 17 CPS preferred French target
- 20 CPS French SDH ceiling
- 2-frame minimum subtitle gap
- machine-readable `output.netflix-report.json`

The formatter must never invent, truncate or silently paraphrase dialogue merely to satisfy layout limits.

See:

- [`docs/NETFLIX_FR_STYLE.md`](docs/NETFLIX_FR_STYLE.md)
- [`docs/SDH_STYLE_GUIDE.md`](docs/SDH_STYLE_GUIDE.md)

## Install

Core/dev installation:

```bash
pip install -e ".[dev]"
```

WhisperX + pyannote runtime:

```bash
pip install -e ".[whisperx,dev]"
```

The WhisperX extra is intentionally optional because it constrains a substantial Torch/CUDA stack. For an existing GPU environment, inspect the dependency plan before upgrading it in place.

### pyannote Community-1 access

The default diarization model is:

```text
pyannote/speaker-diarization-community-1
```

Accept its Hugging Face model conditions, create a read token and export:

```bash
export HF_TOKEN=hf_...
```

Never commit the real token.

## Configuration

`config/settings.yaml` currently enables the real baseline:

```yaml
providers:
  asr: whisperx
  diarization: whisperx_pyannote

whisperx:
  model: large-v3-turbo
  device: auto
  compute_type: float16
  batch_size: 16
  language: null
  vad_method: pyannote
  align: true
  diarize: true
  diarization_model: pyannote/speaker-diarization-community-1
  hf_token_env: HF_TOKEN
  return_embeddings: true
  fill_nearest_speaker: false
```

`device: auto` chooses CUDA when available. On CPU the adapter avoids `float16` and uses an integer compute path.

## Output

Planned/current output files:

- `output.debug.json`
- `output.srt`
- `output.ass`
- `output.netflix-report.json`

The debug JSON now has room for:

- aligned words and confidence
- `speaker_id` at word/segment level
- `speaker_turns`
- `speaker_embeddings`
- overlap evidence
- later OCR/context/router evidence

## Repository map

```text
subtitle_fusion/
├─ README.md
├─ AGENTS.md
├─ pyproject.toml
├─ config/
│  ├─ settings.yaml
│  ├─ scoring.yaml
│  ├─ style_rules.yaml
│  └─ audio_analysis.yaml
├─ docs/
│  ├─ FAST_SCOUT_PIPELINE.md
│  ├─ WHISPERX_PYANNOTE_RUNTIME.md
│  ├─ SDH_STYLE_GUIDE.md
│  ├─ NETFLIX_FR_STYLE.md
│  └─ AUDIO_EVENTS_AND_MUSIC.md
├─ src/
│  ├─ main.py
│  ├─ pipeline.py
│  ├─ models.py
│  ├─ whisperx_provider.py
│  ├─ scoring.py
│  ├─ fusion.py
│  ├─ imdb_index.py
│  ├─ netflix_style.py
│  ├─ exporters.py
│  ├─ audio_music.py
│  └─ track_recognition.py
└─ tests/
   ├─ test_whisperx_provider.py
   ├─ test_scoring.py
   ├─ test_fusion.py
   ├─ test_imdb_index.py
   └─ test_netflix_style.py
```

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

## What is implemented now

- confidence-aware internal word model
- OCR/IMDb candidate fusion primitives
- Netflix French formatter/validator
- SDH policy
- audio/music provider hooks
- WhisperX real media ingestion
- forced word alignment
- pyannote Community-1 diarization
- speaker embeddings
- word/segment speaker IDs
- stable speaker-turn data
- overlap preservation
- provider configuration and lazy optional runtime imports
- unit tests for WhisperX normalization/overlap logic without requiring a GPU

## Next implementation steps

1. build the common timestamped **evidence timeline** and confidence router
2. implement local audio crop + selective re-ASR
3. attach fast OCR detection/recognition to the evidence timeline
4. add persistent show/episode proper-name glossary
5. implement speaker-to-character identity resolution separately from diarization
6. add Moonshine Tiny as an independent fast scout
7. add audio-event/music/singing routing
8. add selective Demucs + vocal ASR
9. add translation + grammar/spelling/context QA reviewer
10. add shot-aware Netflix timing
11. benchmark and calibrate escalation thresholds on real episodes

## Development

```bash
pytest -q
ruff check .
```

Detailed agent instructions live in `AGENTS.md`.
