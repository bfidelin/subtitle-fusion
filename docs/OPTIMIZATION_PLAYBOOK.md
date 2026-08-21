# Optimization playbook and related projects

Last verified: **2026-08-21**.

This document records optimization ideas borrowed at the architecture level from mature subtitle tools. Do not copy implementation code from projects with incompatible licenses; reimplement ideas behind our provider interfaces and cite the inspiration.

## Core performance rule

```text
reuse existing evidence
  -> cheap whole-episode scouts
  -> confidence/quality gate
  -> sparse/local expensive work
  -> deterministic QC/rendering
```

The fastest model call is the one we can safely skip.

## 1. Reference-first ingestion

Before running ASR, inspect the container once with ffprobe/ffmpeg and inventory:
- text subtitle tracks (SRT/ASS/WebVTT/TTML)
- image subtitle tracks (PGS/VobSub)
- audio tracks/languages
- frame rate/time base
- chapters
- duration

Priority:
1. if a good text subtitle track already exists, preserve it as a transcript/timing reference and enrich/correct it instead of retranscribing blindly
2. if an image subtitle track exists, OCR the subtitle bitmaps rather than scanning all video frames for dialogue subtitles
3. run ASR when the existing track is absent, incomplete, wrong-language, or below a quality threshold

This can remove the dominant ASR/OCR cost for many files.

Inspiration:
- ffsubsync can use an already synchronized SRT as reference and reports sub-second synchronization when audio extraction is unnecessary
- ffsubsync 0.5 added PGS reference support and extraction of embedded subtitles in a single ffmpeg pass

References:
- https://github.com/smacke/ffsubsync
- https://github.com/smacke/ffsubsync/blob/master/HISTORY.rst

## 2. Decode once, reuse everywhere

Avoid repeated full-file ffmpeg passes.

Create a media preflight/cache that can expose:
- 16 kHz mono PCM for ASR/diarization/VAD
- 32 kHz or provider-native audio only when a model truly requires it
- shared VAD timeline
- shared shot-boundary timeline
- subtitle stream extracts
- media fingerprint

Where practical, extract multiple needed streams in one ffmpeg invocation or cache the decoded derivative.

Cache key should include:
- media fingerprint (size + mtime + robust content sample/hash)
- stream index
- model/provider version
- relevant configuration hash

Never reuse cached model evidence across incompatible model/config versions.

## 3. Global synchronization preflight

Before word-level re-alignment, run a very cheap global timing sanity check.

### ffsubsync idea

ffsubsync discretizes subtitles and VAD speech into 10 ms speech/non-speech signals and finds the best global offset with FFT convolution (`O(n log n)` rather than a naive `O(n²)` search).

It typically reports 20–30 s total for a video, with raw audio extraction being the expensive part; with an existing subtitle reference it can run in under a second.

Use this idea as a preflight:
- create a binary subtitle-active signal
- reuse the shared VAD signal
- estimate global shift
- optionally estimate simple frame-rate drift
- output a fit/quality score

If quality is already high and offset is tiny, skip expensive re-alignment.

Reference:
- https://github.com/smacke/ffsubsync

### Sparse multi-segment sanity check

ffsubsync 0.5 also introduced multi-segment sync: sample sparse sections across the reference, optionally skip intro/outro, and parallelize. Adopt the principle for long TV episodes:
- sample beginning/middle/end plus several evenly spaced windows
- avoid credits/intro when possible
- infer whether drift is global or piecewise before scanning everything

## 4. Piecewise timing for recaps/cuts/ads

A single offset cannot fix a subtitle made for a different edit.

Alass handles:
- constant offset
- frame-rate differences
- splits caused by ads/director cuts/removed sections

It reports roughly 10–20 s for audio extraction and 5–10 s for alignment in its reference environment.

Borrow the concept of **piecewise alignment with a split penalty**. Detect when a new timing segment is justified instead of continuously warping every cue.

Fast path:
- first test a global shift / rate correction
- only enable split/piecewise search when the fit is poor

Reference:
- https://github.com/kaegi/alass

License note: alass is GPL-3.0. Reimplement the architectural idea; do not copy GPL implementation code into this project unless the repository license is deliberately made compatible.

## 5. Weak scout, strong verifier

A scout does not need final-production accuracy. It needs good recall and cheap inference.

Examples in this architecture:
- tiny VAD -> determine where speech exists
- Paddle mobile/tiny detector -> determine where text may exist
- YAMNet-class classifier -> determine which audio windows deserve PANNs
- low-rate visual face/active-speaker scout -> determine where richer ASD is needed

Route:

```text
cheap score high-confidence negative -> skip
cheap score high-confidence positive -> accept candidate / batch verifier
uncertain -> stronger model
```

Always measure **escalation rate**. A scout that escalates 80% of windows is not saving much.

## 6. OCR: detection is not recognition

Never run full OCR on every video frame.

Default policy:
- shot changes + 0.5 fps periodic baseline
- temporarily rise to 2–5 fps around newly detected text
- use `PP-OCRv5_mobile_det` / `PP-OCRv6_tiny_det` as first detector candidates
- track boxes across frames
- perceptual-hash crops
- OCR only new/changed crops
- choose one/few sharp frames per stable text track
- temporal vote duplicate recognitions
- heavy rotated/perspective detector only on difficult crops

OpenVINO `horizontal-text-detection-0001` remains a useful horizontal specialist and alternative device path.

See `docs/PERFORMANCE_REFERENCES.md`.

## 7. Post-ASR segmentation is its own deterministic stage

Do not let raw Whisper segment boundaries dictate final cues.

Borrow useful concepts from stable-ts without taking a hard runtime dependency:
- split/group on punctuation
- split on meaningful silence/gaps
- use word timestamps for cue boundaries
- suppress timestamps that land deep inside non-speech where evidence supports it
- pad cue boundaries conservatively
- clamp padding to neighboring words/cues so it cannot create overlaps
- split long text after linguistic/silence boundaries before arbitrary character counts
- record regroup operations in debug metadata

stable-ts development was reported paused during this research pass, so treat it as prior art rather than a dependency decision.

Reference:
- https://github.com/jianfch/stable-ts

## 8. Shot map: compute once, use four times

Shot detection is valuable to multiple branches:
- professional cue timing
- OCR sampling
- active-speaker/face-track reset
- detection of recaps/intros/scene discontinuities

Do not run separate scene detectors for each branch.

The shot map should be a timestamped evidence stream with confidence/type and be cached by media fingerprint.

Subtitle Edit provides a mature example of waveform + shot-change workflows, including snap/extend-to-shot-change operations.

References:
- https://github.com/SubtitleEdit/subtitleedit
- https://github.com/SubtitleEdit/subtitleedit/blob/main/docs/overview.md

## 9. Deterministic fix/QC pipeline

Subtitle Edit demonstrates the value of many small deterministic operations instead of one opaque rewrite. Adopt the same philosophy:
- normalize
- merge/split
- balance line breaks
- timing/gap repair
- shot snap
- CPS/WPM warnings
- spelling/duplicate/common-error checks
- render

Every fix should declare whether it is:
- semantic or non-semantic
- safe for automatic application
- reversible/traceable

Keep original text and timings in debug evidence.

Subtitle Edit also exposes both CPS and WPM and has dedicated shot-change tooling; we should report both metrics.

References:
- https://github.com/SubtitleEdit/subtitleedit/blob/main/docs/overview.md
- https://github.com/SubtitleEdit/subtitleedit/blob/main/change-log.txt

## 10. Speaker identity / active speaker

Keep three independent concepts:
- diarization: who sounds different (`SPEAKER_xx`)
- identity: which character voiceprint matches
- visibility: is the matched speaking person visually active/on-screen

Optimization:
- compute voice embeddings once from the diarization backend
- maintain a bounded per-series centroid store
- match with both absolute similarity threshold and best-vs-second-best margin
- run ASD only during speech windows where visibility changes final rendering
- reuse face tracks and reset at shot changes

Never infer off-screen merely because no face was detected.

## 11. Sound/music cascade

```text
shared audio/VAD
  -> cheap AudioSet/YAMNet-class scout
  -> selected windows only
      -> PANNs verifier
      -> music/vocal classifier
      -> track recognition if enabled
      -> Demucs only if vocal separation can improve lyrics/dialogue
```

Batch neighboring candidate windows. Merge repeated sound events before rendering.

## 12. Season/batch scheduling

For a season queue:
- load heavy models once and keep them warm
- process episodes through a worker pipeline instead of launching a Python process/model load per episode
- reuse show glossary and voiceprint centroids
- cap GPU concurrency to avoid VRAM thrash
- allow CPU/iGPU scouts concurrently only when benchmark data shows wall-time improvement
- prefetch/decode the next media file without competing for the bottleneck resource

## 13. Quality gates

Never apply an automatic transformation simply because a model returned a result.

Examples:
- sync correction: reject if fit score is too low, shift implausible, or inferred frame-rate change is outside limits
- voiceprint: require similarity + margin
- OCR: require detector/recognizer confidence + temporal stability for corrections
- translation: require semantic consistency and glossary checks
- source separation: only if candidate window is vocal music and expected benefit is non-trivial

ffsubsync 0.5 explicitly added `--skip-sync-on-low-quality`; adopt the same fail-safe principle globally.

## 14. Benchmark harness

For every provider/stage record:
- cold model load ms
- warm wall time
- preprocessing / inference / postprocessing ms
- RTF for audio stages or FPS/images/s for video stages
- p50/p95 latency where meaningful
- peak CPU RAM / GPU VRAM
- decoded seconds/frames
- frames actually scanned
- candidate/escalation rate
- OCR boxes/tracks/crops
- OCR cache hit ratio
- active-speaker speech-window duration
- audio-event candidate-window duration
- Demucs processed duration
- cache hit/miss reason

Per episode write:
- `output.benchmark.json`
- total wall time and critical-path stage
- estimated time saved by gating/cache when measurable

External benchmark numbers are architecture hints; local warm/cold measurements are the authority.

## 15. Recommended implementation order

1. media preflight: embedded subtitle/audio inventory + shared cache/fingerprint
2. shot map computed once
3. sync/VAD quality preflight and existing-track reuse
4. deterministic segmentation/QC stage with CPS + WPM
5. sparse text detector + crop tracker/cache
6. per-series voiceprint matching
7. YAMNet/scout -> PANNs verifier
8. sparse LR-ASD/active-speaker provider
9. IMSC 1.3 exporter + validation
10. benchmark harness + season worker/model residency
