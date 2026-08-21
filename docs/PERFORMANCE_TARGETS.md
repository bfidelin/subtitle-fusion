# Performance targets and production decisions

Last verified: **2026-08-21**.

This document is the short operational decision record for performance-sensitive work in `subtitle-fusion`.

For the full source list, benchmark details, caveats, papers, GitHub repositories and YouTube demos, read:

- `docs/PERFORMANCE_REFERENCES.md`

The target workload is a **45-minute TV episode**. The objective is to produce enriched SDH subtitles with accurate dialogue timing, speaker identity, useful sound cues, sparse visual text evidence and optional off-screen reasoning without turning the job into a full real-time video-analysis pass.

## Performance objective

Target wall-clock budget after models are warm:

- **fast enriched mode:** about **1.5-3 minutes** for 45 minutes of media
- **rich mode with sparse visual analysis:** about **2-4 minutes**
- expensive fallbacks may increase this, but they must only run on selected windows

This is a target, not a promise. The local benchmark harness is authoritative.

The central rule is:

```text
cheap scout -> candidate window -> stronger verifier -> fusion
```

Do **not** run every expensive model across the whole episode.

## Consolidated benchmark matrix

The 45-minute values below are straight extrapolations of published/reference measurements. They are useful for architecture decisions but are not directly comparable across different GPUs, CPUs, precisions and pipelines.

| Stage | Tool / reference | Published reference | Approx. 45-min equivalent | Production decision |
|---|---|---:|---:|---|
| transcription | faster-whisper large-v2 FP16 batch=8, RTX 3070 Ti | 17 s / 13 min | **~59 s** | keep as primary fast ASR path |
| transcription | faster-whisper large-v2 INT8 batch=8, RTX 3070 Ti | 16 s / 13 min | **~55 s** | excellent low-VRAM option |
| transcription + alignment | WhisperX large-v3, T4, warm | 15.51 s / 5.4 min | **~2m09** | do not retranscribe blindly when fast ASR already exists |
| transcription + alignment | WhisperX large-v3, A10G/L4, warm | ~9.5 s / 5.4 min | **~1m19** | use alignment selectively where possible |
| diarization | pyannote Community-1, H100 | 31-37 s / hour | **~23-28 s** | run in parallel with ASR |
| sound scout | YAMNet baseline, Raspberry Pi 2W | 450-600 ms / 1 s | ~20-27 min continuous on that weak device | desktop timing must be measured; good scout class |
| sound scout | optimized TinyML YAMNet-like, Pi 2W | 180-220 ms / 1 s | ~8-10 min continuous on Pi 2W | proves very cheap scout feasibility |
| sound verifier | PANNs | no comparable modern end-to-end timing found | local benchmark required | keep behind scout / important windows |
| text detection | PP-OCRv5_mobile_det, T4 high-perf | **6.36 ms/image** | **~9 s at 0.5 fps** | preferred general text scout candidate |
| text detection | PP-OCRv5_mobile_det, Xeon CPU high-perf | **28.15 ms/image** | **~38 s at 0.5 fps** | viable CPU-side scout |
| text detection | PP-OCRv6_tiny_det, A100 ORT | 20.49 ms/image end-to-end | local comparison required | benchmark next; only 0.43M params / 1.9 MB |
| text detection | OpenVINO horizontal-text-detection-0001 | ~25.6 FPS async video demo | **~53 s at 0.5 fps** | excellent horizontal specialist / isolated Intel path |
| full OCR | PP-OCRv5 mobile OCR pipeline, V100 | ~0.62 s/image | far too expensive globally | recognize only selected crops |
| active speaker model | LR-ASD | 0.84M params / 0.51 GFLOPs / 94.45% AVA mAP | model-only figure | benchmark before TalkNet |
| active speaker complete pipeline | NVIDIA ASD, A10G | ~54-60 FPS | **~19-21 min** if every 25-fps frame is analyzed | full-frame ASD rejected |
| active speaker complete pipeline | NVIDIA ASD, RTX 4090 | ~72-77 FPS | **~14.6-15.6 min** at every frame | speech-window sparse ASD only |
| source separation | HTDemucs base, Apple M4 | 1.8 s / 7 s | **~11m34** full episode | only selected vocal-music windows |
| source separation | HTDemucs FT, Apple M4 | 6.4 s / 7 s | **~41m09** full episode | never global by default |
| music analysis | Essentia | streaming / algorithm dependent | local benchmark required | use cheap descriptors first |
| identity/fusion/export | voiceprint cosine + Python fusion + JSON/SRT/ASS | lightweight | normally seconds | keep out of critical path |

## Current tool choices

### 1. Dialogue transcription

Preferred strategy:

```text
existing fast faster-whisper path
       |
       +--> good confidence/timing -> keep
       |
       +--> uncertain timing / proper name / difficult window
                 -> WhisperX alignment / targeted refinement
```

Do not replace a sub-minute transcription path with a slower full retranscription merely to obtain metadata.

Primary reference:
- https://github.com/SYSTRAN/faster-whisper

WhisperX:
- https://github.com/m-bain/whisperX
- https://github.com/Ziyang-Liao/WhisperX
- video: https://www.youtube.com/watch?v=zY-8Sr-FzIw

faster-whisper video:
- https://www.youtube.com/watch?v=Kyc0AgMIBSU

### 2. Speaker diarization

Use **pyannote Community-1** in parallel with ASR.

The official H100 benchmark is extremely fast, but consumer GPU timing must be measured locally.

References:
- https://github.com/pyannote/pyannote-audio
- https://www.youtube.com/watch?v=CtjDotATEI0
- https://www.youtube.com/watch?v=wDH2rvkjymY

### 3. Character identity

Use the pyannote speaker embeddings as identity evidence and match them against per-series voiceprints.

Rules:

- cosine score must pass the configured minimum
- the match must also beat the second-best identity by a minimum margin
- unknown is better than a wrong character name
- identity is cached/enrolled across episodes
- voice identity does not imply visual visibility

Expected cost is tiny relative to ASR/vision.

### 4. Sound events

Preferred cascade:

```text
cheap AudioSet scout (YAMNet-class)
        |
        +--> irrelevant / confident -> stop
        |
        +--> important / ambiguous -> PANNs verifier
```

PANNs demos:
- https://www.youtube.com/watch?v=QyFNIhRxFrY
- https://www.youtube.com/watch?v=7TEtDMzdLeY

YAMNet:
- https://www.tensorflow.org/hub/tutorials/yamnet
- https://www.youtube.com/watch?v=DLVA10sb1iE

Only plot-relevant events should become visible SDH cues.

## Video text: detector first, OCR second

This is one of the most important performance decisions.

A 45-minute episode at 25 fps contains:

```text
45 * 60 * 25 = 67,500 frames
```

Full OCR on 67,500 frames is explicitly rejected.

### Preferred text scouts

Benchmark locally in this order:

1. **PP-OCRv5_mobile_det**
2. **PP-OCRv6_tiny_det**
3. **OpenVINO horizontal-text-detection-0001**
4. heavier DBNet/CRAFT/general detectors only as fallbacks

PaddleOCR detector docs:
- https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_detection.en.md

OpenVINO horizontal detector:
- https://docs.openvino.ai/2023.3/omz_models_model_horizontal_text_detection_0001.html
- real-time demo: https://docs.openvino.ai/2024/openvino-workflow/model-server/ovms_demo_horizontal_text_detection.html

### PP-OCRv5_mobile_det arithmetic

Published high-performance T4 detector inference:

```text
6.36 ms/image ~= 157 images/s
```

For 45 minutes:

| Sampling policy | Frames examined | Model-inference projection |
|---|---:|---:|
| every frame at 25 fps | 67,500 | ~7m09 |
| 2 fps | 5,400 | ~34 s |
| 1 fps | 2,700 | ~17 s |
| **0.5 fps** | **1,350** | **~9 s** |

Published high-performance CPU detector inference is 28.15 ms/image (~35.5 FPS):

| Sampling policy | Frames examined | CPU model-inference projection |
|---|---:|---:|
| every 25-fps frame | 67,500 | ~31m40 |
| 1 fps | 2,700 | ~76 s |
| **0.5 fps** | **1,350** | **~38 s** |

These are detector inference projections only. Decode, resize and post-processing still count in the real local benchmark.

### OpenVINO arithmetic

The official asynchronous video demo is around 25.6 FPS at 704x704.

For 45 minutes:

- scan every 25-fps frame: roughly real-time, ~44 minutes
- 1 fps: ~105 seconds
- 0.5 fps: ~53 seconds

OpenVINO remains attractive because it can be isolated from the NVIDIA inference workload and is specifically optimized for mostly horizontal scene text.

### Why recognition must be gated

Full PP-OCRv5 mobile OCR has a reference around **0.62 s/image on V100**.

If we naively OCR the 1,350 images from a 0.5-fps sampler:

```text
1,350 * 0.62 s ~= 837 s ~= 14 minutes
```

So even a sparse sampler is not enough by itself. We must also track and cache text boxes, then OCR only **new or changed crops**.

### Production video-text pipeline

```text
video decoder
   |
   +--> scene cuts
   |
   +--> periodic baseline: 0.5 fps
            |
            v
       fast text detector
            |
       no text -> stop
            |
            +--> new box / changed geometry
            |       -> temporarily raise local sampling to 2-5 fps
            |
            +--> track box across neighboring frames
                    |
                    +--> perceptual hash unchanged
                    |       -> reuse cached OCR
                    |
                    +--> crop new/changed
                            -> choose sharp/key frame
                            -> OCR recognizer
                            -> confidence + temporal voting
                            -> OCRHit evidence
```

Recognition candidates:

- OpenVINO `text-recognition-0014`
- PaddleOCR recognizer
- RapidOCR
- Tesseract only as compatibility fallback

OpenVINO recognizer reference:
- https://docs.openvino.ai/2023.3/omz_models_model_text_recognition_0014.html

Full PP-OCRv5 reference:
- https://openaccess.thecvf.com/content/CVPR2026/supplemental/Cui_PP-OCRv5_A_Specialized_CVPR_2026_supplemental.pdf

## Active speaker / off-screen detection

The network itself is not the only cost. The expensive complete path includes:

- video decode
- face detection
- face tracking
- audio/video buffering
- active-speaker inference

LR-ASD is the preferred first model to benchmark because it is small and has strong published AVA accuracy:

- 0.84M parameters
- 0.51 GFLOPs
- 94.45% AVA validation mAP

References:
- https://github.com/Junhua-Liao/LR-ASD
- https://doi.org/10.1007/s11263-025-02399-2

TalkNet remains a comparison baseline:
- https://github.com/TaoRuijie/TalkNet-ASD
- video: https://www.youtube.com/watch?v=a7rLzt2ZWk0

### Why full-frame ASD is rejected

NVIDIA's complete ASD reference is roughly:

- A10G: 54-60 FPS
- RTX 4090: 72-77 FPS

Even though those rates exceed video playback fps, an offline 45-minute file still contains 67,500 frames. Processing the complete active-speaker pipeline over all of them works out to roughly **15-21 minutes** in those references.

Source:
- https://docs.nvidia.com/nim/maxine/active-speaker-detection/latest/performance-results.html

### Sparse ASD policy

Run ASD only when all of these are useful:

1. speech is present according to ASR/diarization
2. visual visibility matters for the subtitle decision
3. a usable face track exists or can be cheaply established

Initial policy to benchmark:

```text
speech windows only
+ reuse face tracks
+ start around 3-5 fps visual sampling
+ increase locally only around ambiguous speaker changes
```

Illustrative arithmetic: if speech occupies 40% of the episode and ASD samples 5 fps, only about 5,400 frames need the ASD path instead of 67,500. At 60-75 FPS reference throughput that is around **72-90 seconds** before allowing for differences in our face pipeline. This is a planning estimate, not a benchmark claim.

Never infer `speaker_visible=false` merely because a face detector missed a face.

## Music and lyrics

Use Essentia or another cheap music detector/classifier first.

Demucs is only for selected vocal-music windows where lyric recovery matters.

HTDemucs reference on Apple M4:

- base: 1.8 s processing for 7 s audio
- FT: 6.4 s for 7 s

Source:
- https://stemsplitter.github.io/research/model-comparison/

Full-episode source separation is rejected.

For example, the base model ratio is roughly 0.257 processing seconds per media second. If only 60 seconds of useful vocal music need separation, that is roughly 15 seconds on the reference M4 instead of ~11.6 minutes for all 45 minutes.

Demucs:
- https://github.com/facebookresearch/demucs
- video: https://www.youtube.com/watch?v=BttaeQaO80E

Essentia:
- https://essentia.upf.edu/
- https://github.com/MTG/essentia
- video: https://www.youtube.com/watch?v=6e1_6_UCzRw

## Parallel execution plan

Do not sum all benchmark times as if the pipeline were sequential.

The intended runtime is:

```text
                           +--> fast ASR / alignment --------+
                           |                                  |
video/audio extraction ---+--> pyannote --------------------+|
                           |                                 ||
                           +--> sound scout -> verifier -----++
                           |                                  |
                           +--> sparse text scout -> OCR -----+
                           |                                  |
                           +--> sparse ASD -------------------+
                                                              |
                                                              v
                                                    fusion + export
```

The wall-clock time should be primarily bounded by the slowest parallel branch plus synchronization/fusion overhead.

Resource scheduling should avoid putting every task on the same accelerator simultaneously. A likely configuration is:

- NVIDIA GPU: primary ASR, pyannote and selected deep audio/video work, scheduled rather than blindly concurrent if VRAM is tight
- CPU / Intel iGPU / NPU where available: video decode, scene-change detection, text scout or other lightweight gates
- CPU: tracking, perceptual hashing, fusion and export

## Expected 45-minute budget

A reasonable engineering target after warm-up and sparse gating is:

| Branch | Target local budget |
|---|---:|
| audio extraction / decode setup | measure; ideally seconds |
| fast ASR | **< 60 s** |
| alignment refinement | **10-60 s**, preferably selective |
| diarization | **30-90 s** on desktop target hardware |
| sound scout + selected verification | **10-40 s** target |
| text scout | **10-60 s** depending device/sample rate |
| actual OCR recognition | **few seconds to tens of seconds**, because crop cache should dominate |
| sparse ASD | **~30-120 s** target, only when enabled |
| selected Demucs | **0-30 s typical target**, workload dependent |
| voiceprints + fusion + SRT/ASS | **seconds** |

With branches parallelized, the desired total remains approximately **2-4 minutes** for the rich mode rather than the sum of every row.

If local measurements exceed that target, optimize the gate hit rates and video sampling policies before replacing accurate models with weaker ones.

## Required local benchmark harness

External benchmarks are only architecture hints. The project must produce its own measurements on representative episodes.

Every provider invocation should emit timings and counters into a structured benchmark record.

### Global metadata

Record:

- date/time
- git commit SHA
- hostname / machine profile label
- OS
- Python version
- ffmpeg version
- CPU model / core count
- RAM
- GPU model
- CUDA/runtime version
- driver version
- provider/model names and versions
- media duration
- media codec/resolution/fps/audio layout
- cold vs warm run

### Per-stage timing

For every stage record where meaningful:

- `load_ms`
- `preprocess_ms`
- `inference_ms`
- `postprocess_ms`
- `total_ms`
- `rtf`
- `fps`
- `p50_ms`
- `p95_ms`
- `peak_cpu_percent`
- `peak_ram_mb`
- `peak_gpu_mem_mb`

### ASR / diarization counters

Record:

- audio duration
- segment count
- word count
- speaker count
- ASR batch size
- compute type / precision
- alignment duration
- diarization duration
- speaker-embedding duration

### Text/OCR counters

Record:

- source video fps
- frames decoded
- scene cuts
- periodic sample rate
- frames sent to text detector
- detector boxes returned
- stable text tracks created
- temporary high-FPS windows
- crops hashed
- OCR requests
- OCR cache hits
- OCR cache miss rate
- recognizer confidence distribution
- detector time
- recognition time

The most important OCR optimization metric is:

```text
ocr_cache_hit_rate = reused_stable_crops / all_candidate_crops
```

A high cache hit rate is expected for location cards, signs and on-screen UI that remain stable for multiple frames.

### Active-speaker counters

Record:

- total speech duration
- ASD-enabled speech duration
- frames sampled for faces
- face detections
- face tracks
- frames sent to ASD model
- ambiguous speaker transitions
- `speaker_visible=true/false/null` counts
- face-detection time
- tracking time
- ASD inference time

### Audio-event counters

Record:

- scout windows
- verifier windows
- escalation rate
- event counts by class
- scout time
- verifier time

A key metric is:

```text
verifier_escalation_rate = verifier_windows / scout_windows
```

If this is too high, the scout/gating policy is not saving enough work.

### Music counters

Record:

- music windows
- vocal-music windows
- Demucs windows
- separated media duration
- Demucs processing time
- track-recognition queries

### Output benchmark artifact

Each run should write something like:

```text
out/<episode>/benchmark.json
```

Example shape:

```json
{
  "media_duration_sec": 2700.0,
  "wall_clock_ms": 142500,
  "stages": {
    "asr": {"total_ms": 48700, "rtf": 0.018},
    "diarization": {"total_ms": 62100, "rtf": 0.023},
    "text_detection": {
      "total_ms": 14200,
      "frames_scanned": 1365,
      "boxes": 84
    },
    "ocr": {
      "total_ms": 7100,
      "requests": 21,
      "cache_hits": 63
    },
    "asd": {
      "total_ms": 80100,
      "frames_scanned": 5100
    }
  }
}
```

The values above are illustrative only.

## Performance regression policy

Codex/Pi changes touching providers or orchestration should not be accepted solely because tests pass.

For performance-sensitive changes:

1. run the unit/CI suite
2. run at least one representative benchmark episode when the heavy runtime is available
3. compare wall-clock and stage timings against the previous baseline
4. explain regressions greater than **10%** on an important stage
5. do not trade substantial subtitle quality for small benchmark wins without an explicit policy decision

The benchmark harness should eventually support a command similar to:

```bash
subtitle-fusion benchmark \
  --video episode.mkv \
  --profile rich \
  --repeat 3 \
  --output benchmark.json
```

and a comparison command:

```bash
subtitle-fusion benchmark-compare baseline.json candidate.json
```

## Implementation priority

Current performance-oriented implementation order:

1. **Paddle mobile/tiny text scout provider**
2. text-box tracking + perceptual crop hash + OCR cache
3. OCR recognizer adapter for selected crops
4. benchmark harness + `benchmark.json`
5. cheap sound scout before PANNs verification
6. LR-ASD provider with sparse speech-window scheduling
7. Demucs/lyrics only on selected vocal-music windows
8. tune accelerator scheduling after real local measurements

Do not optimize speculative bottlenecks ahead of measured ones.
