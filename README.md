# subtitle-fusion

Fast, production-oriented **enriched SDH subtitle** pipeline for TV/movies.

The project combines WhisperX/Faster-Whisper, pyannote diarization, proper-name/context evidence, sparse OCR, audio/music analysis, speaker identity, professional timed-text QC and SRT/ASS output.

The performance rule is:

> **Reuse evidence first; scout cheaply; spend expensive compute only where it can change the result.**

## Current runtime baseline

Implemented today:
- WhisperX batched Faster-Whisper ASR
- VAD-aware transcription and forced word alignment
- word timestamps/scores
- pyannote `speaker-diarization-community-1`
- stable episode-local speaker IDs, turns, embeddings and overlap evidence
- Netflix-style French formatter/validator + compliance JSON
- conservative evidence/fusion primitives
- optional PANNs audio-event verifier adapter
- per-series conservative voiceprint store
- ffprobe media/subtitle-track preflight
- SRT, ASS and debug JSON exports

Do **not** add another whole-episode Faster-Whisper pass before WhisperX: WhisperX already uses Faster-Whisper internally. Any extra ASR should normally be selective/local.

### Reference-first ingestion status

`src/media_preflight.py` already inventories the container before expensive work. It records audio streams and text/image subtitle tracks in debug evidence.

The next step is **not** another media scanner. It is a quality-gated source selector:

```text
embedded text track
  -> language / coverage / timing / VAD-sync / lexical quality score
       | high quality + good sync
       +-----------------------> reuse + enrich
       |
       | high quality + simple offset/drift
       +-----------------------> repair sync -> reuse + enrich
       |
       | alternate edit / piecewise mismatch
       +-----------------------> piecewise alignment
       |
       ` low quality / wrong language / incomplete
                                -> WhisperX baseline
```

Until that quality gate is implemented, the presence of an embedded subtitle track must **not** automatically suppress WhisperX.

## New reference architecture

```text
MKV / MP4
   |
   +-> ffprobe preflight
   |     +-> good text subtitle track? -> reuse/enrich
   |     +-> PGS/image subtitles?      -> event-level OCR first
   |     +-> otherwise                 -> ASR baseline
   |
   +-> shared evidence/cache
         audio + VAD + shot map + subtitle inventory
              |
       +------+------+----------------+
       |             |                |
   WhisperX       sparse OCR       audio scout
   + pyannote     detector         -> verifier
       |             |                |
       +------ timestamped evidence --+
                         |
                 confidence router
                         |
             local expensive fallbacks
                         |
              deterministic subtitle QC
                         |
         debug JSON + SRT + ASS + future IMSC
```

## Professional standards

Read these first:
- [`docs/STANDARDS_AND_PRACTICES.md`](docs/STANDARDS_AND_PRACTICES.md) — Netflix fr-FR, SDH, translation, shot timing, QC, W3C/EBU
- [`docs/TRANSLATOR_QC_CHECKLIST.md`](docs/TRANSLATOR_QC_CHECKLIST.md) — practical translator/reviewer workflow and quality gates
- [`docs/OPTIMIZATION_PLAYBOOK.md`](docs/OPTIMIZATION_PLAYBOOK.md) — ffsubsync, Alass, Subtitle Edit, stable-ts ideas and production optimization
- [`docs/PERFORMANCE_TARGETS.md`](docs/PERFORMANCE_TARGETS.md) — 45-minute wall-clock targets and provider decisions
- [`docs/PERFORMANCE_REFERENCES.md`](docs/PERFORMANCE_REFERENCES.md) — benchmark sources and useful videos
- [`docs/FAST_SCOUT_PIPELINE.md`](docs/FAST_SCOUT_PIPELINE.md) — confidence-routing architecture
- [`docs/WHISPERX_PYANNOTE_RUNTIME.md`](docs/WHISPERX_PYANNOTE_RUNTIME.md) — current heavy runtime
- [`docs/NETFLIX_FR_STYLE.md`](docs/NETFLIX_FR_STYLE.md) and [`docs/SDH_STYLE_GUIDE.md`](docs/SDH_STYLE_GUIDE.md)

### Netflix-style fr-FR highlights

Current profile/QC includes:
- 42 visible chars max per line
- max 2 lines
- clause-aware / bottom-heavy wrapping where possible
- 20-frame minimum duration and 7 s maximum
- 2-frame minimum gap
- 17 CPS normal French target / 20 CPS SDH ceiling profile
- machine-readable compliance report

The important next timing extension is **shot-aware timing**. Subtitle boundaries must use both the waveform and edit/shot structure; a formatter may not silently rewrite meaning to make metrics pass.

### Standards master direction

SRT remains the compatibility-first playback target and ASS the rich local target. For a standards-based rich interchange/archive format, the project direction is **W3C IMSC Text Profile 1.3 (TTML2)**, which became a W3C Recommendation in May 2026. Do not claim IMSC compliance until the exporter and validator exist.

## Translation and proofreading

Translation is a separate semantic stage, not a formatter side effect. The intended sequence is:

```text
source/template choice
 -> glossary + proper names
 -> translation candidate
 -> semantic/context review
 -> grammar/spelling/punctuation review
 -> subtitle adaptation
 -> SDH/forced-narrative review
 -> shot-aware timing
 -> final QC
```

Keep independent confidence for ASR, OCR, proper names, source-track quality, synchronization, translation semantics and linguistic QA. A high score in one dimension does not cancel a contradiction in another.

See [`docs/TRANSLATOR_QC_CHECKLIST.md`](docs/TRANSLATOR_QC_CHECKLIST.md).

## Fast OCR

Full OCR on every frame is explicitly rejected.

Initial policy:
```text
shot changes + ~0.5 fps baseline
  -> PP-OCR mobile/tiny detector
  -> track boxes
  -> perceptual hash crops
  -> OCR only new/changed crops
  -> temporal voting
```

Local detector order to benchmark:
1. `PP-OCRv5_mobile_det`
2. `PP-OCRv6_tiny_det`
3. OpenVINO `horizontal-text-detection-0001`

Around newly appearing text, temporarily increase sampling to roughly 2–5 fps, then drop back down after the text track stabilizes.

## Speaker identity

Keep these separate:
```text
speaker_id       = acoustic diarization cluster
character_name   = voice/context identity hypothesis
speaker_visible  = active-speaker/visual evidence
```

`src/voiceprints.py` stores bounded per-series samples and requires both an absolute cosine threshold and a margin over the second-best identity. Weak matches remain unknown.

A failed face detector is **not** proof that speech is off-screen.

## Audio / music

Target cascade:
```text
cheap YAMNet/AudioSet-class scout
  -> candidate windows only
  -> PANNs verifier
  -> music/vocal analysis
  -> track recognition if enabled
  -> Demucs only on selected vocal-music windows
```

Never run Demucs over a complete episode by default.

## Performance objective

Reference workload: 45-minute episode, warm models.
- fast enriched mode: **~1.5–3 min** engineering target
- rich sparse visual mode: **~2–4 min** engineering target

These are targets, not promises. The planned benchmark harness will record stage timing, RTF/FPS, memory, escalation/cache rates and critical path in `output.benchmark.json`.

### Season/batch objective

For a season queue, heavy models should be loaded once and reused:

```text
load WhisperX / pyannote / OCR / audio models once
              |
       E01 -> E02 -> E03 -> ...
              |
      shared show glossary
      shared voiceprints
      bounded caches
```

Do not pay model cold-start cost once per episode. Bound GPU concurrency to avoid VRAM thrash; prefetch/decode only when it does not compete with the critical GPU stage.

## Install

Core/tests:
```bash
pip install -e '.[dev]'
ruff check .
pytest -q
```

WhisperX runtime:
```bash
pip install -e '.[whisperx,dev]'
export HF_TOKEN=hf_...
```

Optional audio verifier:
```bash
pip install -e '.[audio]'
```

Accept the Hugging Face conditions for `pyannote/speaker-diarization-community-1` before using diarization.

## Run

```bash
subtitle-fusion run \
  --video /path/video.mkv \
  --title "Example Show" \
  --season 1 \
  --episode 3 \
  --imdb-title-id tt1234567 \
  --output-dir ./out
```

Current outputs:
- `output.debug.json`
- `output.srt`
- `output.ass`
- `output.netflix-report.json` when the Netflix profile is enabled

## Next implementation order

1. select/extract/reuse existing subtitle tracks with language/coverage/sync/quality gates (**preflight inventory is already implemented**)
2. compute/cache one shot map and reuse it for timing + OCR + ASD
3. add cheap VAD/global sync quality preflight, then piecewise fallback for alternate edits
4. make post-ASR segmentation/QC deterministic with CPS + WPM + shot-aware rules
5. implement sparse Paddle text detector + track/cache + crop recognizer
6. connect voiceprints to character identity enrollment/matching
7. connect YAMNet-class scout -> PANNs verifier
8. add sparse LR-ASD active-speaker provider
9. add IMSC 1.3 exporter + validator
10. add benchmark harness and warm season worker/model residency

Agent rules are in [`AGENTS.md`](AGENTS.md).
