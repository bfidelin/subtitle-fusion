# Performance targets and production decisions

Last verified: **2026-08-21**.

Read `docs/PERFORMANCE_REFERENCES.md` for source measurements and `docs/OPTIMIZATION_PLAYBOOK.md` for the architecture rationale.

## Target workload

Reference workload: **45-minute TV episode**.

Warm wall-clock objectives:
- fast enriched mode: **1.5–3 minutes**
- rich mode with sparse visual/OCR analysis: **2–4 minutes**

The local benchmark harness is authoritative. Never weaken subtitle quality merely to hit a timing target.

## Critical-path architecture

```text
media preflight / embedded subtitle inventory
            |
     shared cached evidence
  (audio, VAD, shot map, tracks)
            |
  +---------+----------+----------------+
  |                    |                |
WhisperX           text scout       audio scout
ASR+align+         sparse OCR       -> verifier
pyannote           detection        only candidates
  |                    |                |
  +--------- evidence timeline --------+
                    |
             selective fallbacks
                    |
             deterministic QC
                    |
        SRT / ASS / future IMSC
```

Do not sum standalone model times when branches can safely run in parallel, but do not create GPU contention that makes the critical path slower.

## Production decisions

### ASR
- current baseline: WhisperX, which already uses Faster-Whisper internally
- do not add a duplicate whole-episode Faster-Whisper pass
- extra ASR is local/selective unless benchmark evidence proves a second global pass helps
- keep raw words/timestamps/confidences

### Diarization
- pyannote Community-1 remains the baseline through WhisperX
- preserve speaker turns, embeddings and overlap evidence
- identity matching is a downstream layer, not diarization

### Existing subtitle tracks
Before ASR, inspect embedded tracks. A trustworthy text subtitle track may become a timing/transcript reference and avoid redundant work. PGS/image subtitles should be OCRed at subtitle-event level before considering arbitrary whole-frame OCR.

### Sync preflight
Add a cheap VAD/subtitle global synchronization score before expensive word-level timing repair. Prefer global shift/rate correction first; only use piecewise alignment when quality indicates cuts/ads/alternate edits.

### OCR
Local benchmark order:
1. `PP-OCRv5_mobile_det`
2. `PP-OCRv6_tiny_det`
3. OpenVINO `horizontal-text-detection-0001`

Policy:
- scene cuts + 0.5 fps periodic baseline
- adaptive 2–5 fps only around newly detected text
- track boxes
- hash crops
- OCR new/changed crops only
- temporal voting

Full OCR on every frame is forbidden as a normal path.

### Shot detection
Compute one shot map and reuse it for:
- Netflix timing
- OCR sampling
- ASD/face-track refresh
- structural discontinuity detection

### Audio events
Target cascade:
- cheap YAMNet/AudioSet-class scout over broad audio
- PANNs verification on candidate windows
- merge duplicate/repeated events
- allowlist plot-relevant visible labels

### Active speaker
Benchmark LR-ASD before TalkNet. Run only on speech windows where visibility changes final subtitle rendering. Reuse face tracks. Never map `no face` directly to `off-screen`.

### Music / Demucs
Do not run source separation over an entire episode. Trigger only on vocal-music windows where separation can improve intelligible lyrics/dialogue.

### Voiceprints
Use per-series centroids with:
- absolute similarity threshold
- margin over second-best identity
- bounded sample history
- explicit unknown result when confidence is weak

### Model residency / batch queue
For season/library processing:
- load heavy models once
- keep them warm across episodes
- reuse show glossary and voiceprints
- bound GPU concurrency
- cache media-derived evidence

## Initial timing budget by branch

These are design budgets, not hard promises:

| Branch | Desired 45-min budget |
|---|---:|
| WhisperX ASR/alignment | <= ~1–2 min warm on target GPU |
| diarization overhead | overlap with ASR where implementation permits; otherwise keep well below ASR cost |
| sparse text detection | seconds to <1 min |
| actual OCR recognition | only a small fraction of detector frames |
| sound scout/verifier | below ASR critical path |
| voiceprints/fusion/QC/export | seconds |
| sparse ASD | <= ~1–2 min additional in rich mode |
| Demucs | proportional only to selected music duration |

## Benchmark harness contract

Per run write `output.benchmark.json` with:
- media duration/fps/resolution/audio streams
- git commit and config hash
- provider/model versions
- device/precision/batch size
- cold model-load time
- warm stage wall time
- preprocess/inference/postprocess split where available
- RTF or FPS
- peak RAM/VRAM when measurable
- frames/audio seconds actually analyzed
- scout escalation rates
- cache hit/miss counts and reasons
- OCR detector frames / tracks / recognition crops / cache ratio
- ASD speech duration / frames/faces processed
- PANNs candidate duration
- Demucs processed duration
- total wall time and critical path

For comparative runs, report delta in both quality metrics and time. A faster change that increases errors or unsafe corrections is not an optimization.

## Quality/performance acceptance

A performance-sensitive change is accepted when:
- core tests/lint pass
- no raw evidence is lost
- output semantics are unchanged or deliberately documented
- local benchmark improves wall time/resource use or enables a justified quality gain
- fallback/escalation rate remains bounded
- quality gate rejects implausible automatic corrections

## Next implementation sequence

1. media preflight + existing-track inventory/cache
2. shared shot map
3. global sync/VAD quality preflight
4. deterministic segmentation + expanded QC (CPS/WPM/shot-aware)
5. sparse OCR detector/tracker/cache
6. voiceprint integration
7. audio scout -> PANNs verifier
8. sparse active-speaker provider
9. IMSC 1.3 exporter/validator
10. benchmark harness + season worker/model residency
