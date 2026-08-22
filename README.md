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
              debug JSON + SRT
                   + optional ASS
```

## Professional standards

Read these first:
- [`docs/STANDARDS_AND_PRACTICES.md`](docs/STANDARDS_AND_PRACTICES.md) — Netflix fr-FR, SDH, translation, shot timing, QC, W3C/EBU
- [`docs/SDH_SEMANTICS_AND_SPEAKER_ROLES.md`](docs/SDH_SEMANTICS_AND_SPEAKER_ROLES.md) — narrator/voice-over/off-screen roles, locale-aware SDH punctuation, sparse visual identity and active-speaker fusion
- [`docs/TRANSLATOR_QC_CHECKLIST.md`](docs/TRANSLATOR_QC_CHECKLIST.md) — practical translator/reviewer workflow and quality gates
- [`docs/OPTIMIZATION_PLAYBOOK.md`](docs/OPTIMIZATION_PLAYBOOK.md) — ffsubsync, Alass, Subtitle Edit, stable-ts ideas and production optimization
- [`docs/PERFORMANCE_TARGETS.md`](docs/PERFORMANCE_TARGETS.md) — 45-minute wall-clock targets and provider decisions
- [`docs/PERFORMANCE_REFERENCES.md`](docs/PERFORMANCE_REFERENCES.md) — benchmark sources and useful videos
- [`docs/FAST_SCOUT_PIPELINE.md`](docs/FAST_SCOUT_PIPELINE.md) — confidence-routing architecture
- [`docs/AUDIO_EVENTS_AND_MUSIC.md`](docs/AUDIO_EVENTS_AND_MUSIC.md) — audio events, music, singing and selective source separation
- [`docs/SONG_IDENTIFICATION.md`](docs/SONG_IDENTIFICATION.md) — identify songs from sung-word fragments + fingerprint evidence
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

### SDH semantic model

Do not preserve source punctuation blindly across locales. Parse the semantic event first, then render it according to the active profile.

Examples:

```text
two speakers            -> locale-specific hyphen syntax
abrupt interruption     -> `--` in en-US / `…` in fr-FR Netflix profile
hesitation/trail-off     -> ellipsis semantics
[narrator]               -> speaker-role evidence
[scoffs]                 -> sound-event evidence
Mm-hmm / Uh / Um         -> paralinguistic speech evidence
quoted speech            -> quote state preserved across cue segmentation
```

Speaker labels may appear on a separate physical SRT line or inline with dialogue; both should normalize to the same internal evidence.

### SRT-first output policy

**SRT is the primary playback format for this project.** The rich evidence model remains internal/debug data; it does not require a rich playback format.

For Jellyfin/Android TV compatibility, dynamic placement can later be emitted as SRT positioning extensions where supported, for example:

```srt
{\an8}Subtitle moved to the top to avoid on-screen text.
```

The intended placement engine will use OCR/text boxes, shot continuity and later face/important-region evidence to choose a stable region and avoid ping-pong between top/bottom. This positioning logic is **planned, not implemented yet**.

ASS remains optional. **IMSC/TTML is deliberately inactive and deferred:** there is no exporter, no dependency, no generated IMSC file and no active implementation task. It may remain documented only as standards research/reference unless explicitly re-enabled later.

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

The same OCR/text bounding boxes should later feed the SRT placement engine, so text detection can both recognize on-screen content and tell the renderer where **not** to place dialogue subtitles.

## Speaker identity, role and visual evidence

Keep these separate:

```text
speaker_id       = acoustic diarization cluster
character_name   = voice/context identity hypothesis
speaker_role     = dialogue | narrator | voice_over | announcer | ...
speaker_visible  = visual evidence
active_face      = face track currently speaking, if known
```

`src/voiceprints.py` stores bounded per-series samples and requires both an absolute cosine threshold and a margin over the second-best identity. Weak matches remain unknown.

A failed face detector is **not** proof that speech is off-screen. Likewise, off-screen speech is not automatically voice-over, and voice-over is not automatically narrator.

Narrator/role resolution should fuse:
- trusted source labels such as `[narrator]`
- recurrent role voiceprints
- contextual LLM classification over neighboring cues
- structural intro/recap/transition/outro context
- visual/active-speaker evidence

The LLM is one evidence source, not an authority.

### Sparse visual sampling

Do not recognize faces on every frame. Visual identity should be triggered by the events that matter:

```text
new shot
speaker turn start  -> sample ~+200/300 ms inside speech
speaker turn end    -> sample ~-200/300 ms inside speech
shot change during speech
speaker change / overlap
long turn midpoint only if needed
face-track loss/new face
```

At cuts, prefer a clean representative frame shortly after the transition over the exact cut frame. Face detection, face identity and active-speaker detection remain separate stages. LR-ASD is the preferred first active-speaker candidate, run only on speech windows while reusing face tracks.

See [`docs/SDH_SEMANTICS_AND_SPEAKER_ROLES.md`](docs/SDH_SEMANTICS_AND_SPEAKER_ROLES.md).

## Audio / music

Target cascade:
```text
cheap YAMNet/AudioSet-class scout
  -> candidate windows only
  -> PANNs verifier
  -> music/vocal analysis
  -> selected vocal window
       +-> vocal ASR -> distinctive lyric fragments -> web candidate search
       +-> Chromaprint/AcoustID when useful
       +-> fuse candidates -> MusicBrainz metadata confirmation
  -> Demucs/HTDemucs only where vocal isolation can improve the result
```

Lyrics search is an **identification/context tool**, not a license to download or replace subtitles with full web lyrics. Keep only short query fragments, candidate metadata and confidence evidence. A network lookup failure must not block normal subtitle generation.

Never run Demucs over a complete episode by default.

Opening/ending themes should eventually be learned as local recurring fingerprints after high-confidence identification, so later episodes can recognize them without repeated web lookup or source separation.

See [`docs/AUDIO_EVENTS_AND_MUSIC.md`](docs/AUDIO_EVENTS_AND_MUSIC.md) and [`docs/SONG_IDENTIFICATION.md`](docs/SONG_IDENTIFICATION.md).

## Performance objective

Reference workload: 45-minute episode, warm models.
- fast enriched mode: **~1.5–3 min** engineering target
- rich sparse visual mode: **~2–4 min** engineering target

These are targets, not promises. The planned benchmark harness will record stage timing, RTF/FPS, memory, escalation/cache rates and critical path in `output.benchmark.json`.

### Season/batch objective

For a season queue, heavy models should be loaded once and reused:

```text
load WhisperX / pyannote / OCR / audio / vision models once
              |
       E01 -> E02 -> E03 -> ...
              |
      shared show glossary
      shared voiceprints/role memory
      recurring theme fingerprints
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

No IMSC/TTML file is generated.

## Next implementation order

1. select/extract/reuse existing subtitle tracks with language/coverage/sync/quality gates (**preflight inventory is already implemented**)
2. compute/cache one shot map and reuse it for timing + OCR + ASD/vision
3. add cheap VAD/global sync quality preflight, then piecewise fallback for alternate edits
4. make post-ASR segmentation/QC deterministic with CPS + WPM + shot-aware + SDH semantic rules
5. implement sparse Paddle text detector + track/cache + crop recognizer
6. add collision-aware SRT placement using OCR/shot evidence
7. connect voiceprints to character identity and bounded narrator/role enrollment
8. add contextual speaker-role resolver (`narrator`, `voice_over`, `off_screen`, `announcer`, etc.)
9. connect YAMNet-class scout -> PANNs verifier
10. add sparse face detector/tracker/embedding identity path sampled from shots + speaker turns
11. add sparse LR-ASD active-speaker provider and multimodal face/voice/context fusion
12. add lyric-fragment song identification + optional AcoustID/MusicBrainz confirmation + recurring theme memory
13. add benchmark harness and warm season worker/model residency

IMSC is intentionally **not** in the active roadmap.

Agent rules are in [`AGENTS.md`](AGENTS.md).
