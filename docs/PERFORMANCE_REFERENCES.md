# Performance references and fast-path design

Last verified: **2026-08-21**.

This document is the performance decision record for `subtitle-fusion`. Numbers are reference measurements from the linked sources, **not promises for local hardware**. Hardware, precision, batch size, preprocessing, decoding, cold start and model versions matter.

## Executive benchmark matrix

For comparable audio tools, `RTF` means processing_time / media_duration (lower is better). The 45-minute column is a straight extrapolation from the cited benchmark and should only be compared when hardware and workload are similar.

| Stage | Reference benchmark | Approx. 45-min equivalent | Confidence / important caveat |
|---|---:|---:|---|
| faster-whisper large-v2 FP16 batch=8 | 17 s / 13 min on RTX 3070 Ti | ~59 s | Official project benchmark; transcription only |
| faster-whisper large-v2 INT8 batch=8 | 16 s / 13 min on RTX 3070 Ti | ~55 s | Official project benchmark |
| WhisperX large-v3 + alignment, T4 | 15.51 s / 5.4 min | ~2m09 | Warm model; third-party WhisperX benchmark |
| WhisperX large-v3 + alignment, A10G | 9.53 s / 5.4 min | ~1m19 | Warm model |
| WhisperX large-v3 + alignment, L4 | 9.44 s / 5.4 min | ~1m19 | Warm model |
| pyannote Community-1, H100 | 31-37 s / 1 h | ~23-28 s | Official H100 self-hosted benchmark |
| YAMNet baseline, Raspberry Pi 2W | 450-600 ms / 1 s clip | ~20-27 min if run continuously | Weak embedded device; do not extrapolate to desktop GPU |
| optimized TinyML YAMNet-like model, Pi 2W | 180-220 ms / 1 s clip | ~8-10 min if run continuously | Shows scout feasibility on weak hardware, not our expected desktop timing |
| PANNs | no trustworthy modern apples-to-apples runtime found | local benchmark required | Keep as verifier, not budgeted yet |
| PP-OCRv5_mobile_det, T4 high-performance | 6.36 ms model inference / image | see video table below | Official PaddleOCR detector benchmark, inference only |
| PP-OCRv5_mobile_det, CPU high-performance | 28.15 ms model inference / image | see video table below | Xeon Gold 6271C, 8-thread high-performance path |
| PP-OCRv6_tiny_det, A100 ONNXRuntime | 20.49 ms end-to-end / image | see video table below | 0.43M params / 1.9 MB; different hardware and test setup |
| OpenVINO horizontal-text-detection-0001 demo | ~25.6 FPS reported | see video table below | Full async client/server demo at 704x704, mostly horizontal text |
| full PP-OCRv5 mobile OCR pipeline, V100 | 0.62 s / image | far too expensive per video frame | Detection + recognition pipeline; proves why recognition must be gated |
| LR-ASD | 0.84M params, 0.51 GFLOPs, 94.45% AVA mAP | model-only runtime is not pipeline runtime | Very light ASD candidate; face detection/tracking still costs time |
| NVIDIA end-to-end ASD, A10G | ~54-60 FPS single stream | ~19-21 min for every 25-fps frame | Includes more of the real video pipeline |
| NVIDIA end-to-end ASD, RTX 4090 | ~72-77 FPS single stream | ~14.6-15.6 min for every 25-fps frame | Strong evidence that full-frame ASD must be sparse |
| HTDemucs base, Apple M4 | 1.8 s / 7 s | ~11m34 | Only use on selected music windows |
| HTDemucs FT, Apple M4 | 6.4 s / 7 s | ~41m09 | Never run blindly over a whole episode |
| Essentia | designed for real-time / streaming use | local algorithm-specific benchmark required | No generic runtime because cost depends on selected algorithms |
| voiceprint cosine matching + fusion/export | tiny compared with ML stages | local benchmark required | Pure Python/data work; keep out of critical path |

## Video-text scout: updated decision

### Short answer

**Yes, text detection can be very fast. Full OCR is the expensive part.**

The best current published scout number found in this research pass is PaddleOCR's lightweight detector:

- `PP-OCRv5_mobile_det`
- model size: 4.7 MB
- T4 inference: 10.67 ms standard / **6.36 ms high-performance**
- Xeon Gold 6271C inference: 57.77 ms standard / **28.15 ms high-performance**
- benchmark set: 2677 multilingual/multi-scenario images

Source:
- https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_detection.en.md

The newer `PP-OCRv6_tiny_det` is even smaller:

- **0.43M parameters**
- **1.9 MB** model
- current A100 + ONNXRuntime end-to-end reference: **20.49 ms/image** (including pre/post processing in that engine benchmark)

Because the v5/T4 table and v6/A100 table use different hardware/test paths, do not claim v6 is faster or slower from those numbers alone. Benchmark both locally.

### 45-minute video implications

A 45-minute 25-fps episode contains **67,500 frames**.

If every frame were analyzed, even a fast detector wastes time. Using the official `PP-OCRv5_mobile_det` high-performance T4 inference figure (~157 FPS, model-only):

- all 25-fps frames: ~7.2 minutes of model inference
- sample at 2 fps: ~34 s
- sample at 1 fps: ~17 s
- sample at 0.5 fps: ~9 s

Using the published CPU high-performance figure (~35.5 FPS, model-only):

- all 25-fps frames: ~31.7 minutes
- sample at 1 fps: ~76 s
- sample at 0.5 fps: ~38 s

These are arithmetic projections from **model inference only**; decoding, resizing and post-processing add overhead.

### OpenVINO remains useful

`horizontal-text-detection-0001` is still a good horizontal-text specialist:

- ~7.78 GFLOPs
- ~2.26M parameters
- input 704x704
- ICDAR2013 F-measure 88.45%
- OpenVINO explicitly describes it as much faster than `text-detection-0003/0004`

The official OVMS real-time demo reports approximately **25.6-25.7 FPS** with asynchronous requests and ~131-141 ms request latency at 704x704. Do not multiply the per-thread FPS lines as if they were independent full-stream throughput without reproducing the setup.

References:
- https://docs.openvino.ai/2023.3/omz_models_model_horizontal_text_detection_0001.html
- https://docs.openvino.ai/2024/openvino-workflow/model-server/ovms_demo_horizontal_text_detection.html
- https://docs.openvino.ai/2023.3/omz_demos_text_detection_demo_cpp.html
- https://docs.openvino.ai/2026/documentation/compatibility-and-support/supported-models.html

At 25.6 FPS, a naive full 25-fps scan is roughly real-time (~44 min of detector throughput for a 45-min episode). Sparse sampling changes the economics:

- 1 fps sample: ~105 s
- 0.5 fps sample: ~53 s

Again, this is based on the published client/server demo, not a direct local `benchmark_app` result.

### Which scout should subtitle-fusion use?

Preferred order to benchmark locally:

1. **PP-OCRv5_mobile_det**: strongest current speed evidence on T4 + CPU and handles general text orientation/scenes better than a horizontal-only model.
2. **PP-OCRv6_tiny_det**: extremely small next-generation candidate; benchmark locally because official current speed table uses A100.
3. **OpenVINO horizontal-text-detection-0001**: excellent simple horizontal specialist and useful alternative when isolating text detection from the NVIDIA workload.
4. heavier DB/CRAFT/general detectors only when the scout reports uncertainty or text geometry demands it.

## Recognition after detection

Do not confuse text detection with OCR recognition.

OpenVINO `text-recognition-0014` is small (tight aligned crop input, 32x128):

- ~0.273 GFLOPs
- ~1.42M parameters

Reference:
- https://docs.openvino.ai/2023.3/omz_models_model_text_recognition_0014.html

Paddle's **full PP-OCRv5 mobile OCR pipeline** is much more expensive than the detector alone. CVPR 2026 supplementary measurements report about:

- 0.62 s/image on Tesla V100
- 1.75 s/image on Xeon Gold 6271C

This is why `subtitle-fusion` must recognize **only new/changed text crops**, not every sampled frame.

References:
- https://openaccess.thecvf.com/content/CVPR2026/supplemental/Cui_PP-OCRv5_A_Specialized_CVPR_2026_supplemental.pdf
- https://www.paddleocr.ai/v3.3.0/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html

## Proposed video-text pipeline

```text
video decoder
   |
   +--> scene changes + sparse periodic samples (start with 0.5-1 fps)
           |
           v
 fast text scout
 (PP-OCRv5 mobile / PP-OCRv6 tiny / OpenVINO horizontal)
           |
     no boxes --> stop
           |
           +--> track boxes across neighboring frames
           |
           +--> perceptual hash / crop-change check
                     |
            unchanged --> reuse cached OCR
                     |
             new/changed --> recognize tight crop
                               |
                    OpenVINO text-recognition-0014
                    or Paddle/RapidOCR recognizer
                               |
                    confidence + temporal voting
                               |
                    OCRHit / proper-name evidence
```

Important optimizations:

- trigger at scene cuts plus a low periodic sample rate
- track stable boxes instead of redetecting every frame
- perceptual-hash crops and skip recognition when unchanged
- recognize one or a few sharp frames per stable text track
- use temporal voting across duplicate observations
- preserve raw OCR candidates and confidence
- use IMDb/dialogue context only after visual OCR evidence exists

## ASR: faster-whisper

Project / official benchmark:
- https://github.com/SYSTRAN/faster-whisper

RTX 3070 Ti 8GB, CUDA 12.4, large-v2, 13 minutes audio:

- FP16 batch=8: 17 s, 6090 MB VRAM
- INT8 batch=8: 16 s, 4500 MB VRAM

Useful video:
- https://www.youtube.com/watch?v=Kyc0AgMIBSU

Design: preserve the existing fast ASR path. Do not retranscribe just to gain metadata.

## Alignment: WhisperX

Official project:
- https://github.com/m-bain/whisperX

Performance reference used here:
- https://github.com/Ziyang-Liao/WhisperX

Warm large-v3 FP16, batch 32, transcription + alignment, 5.4-minute file:

- T4: 15.51 s (21.0x real-time)
- A10G: 9.53 s (34.1x)
- L4: 9.44 s (34.5x)

Important real-world warning: alignment speed varies heavily by language/model. A 2025 WhisperX issue reports ~41 s alignment for 35 minutes plus ~26 s diarization in one setup; older reports show much worse alignment on some language models. Measure the actual target languages.

References:
- https://github.com/m-bain/whisperX/issues/1287
- https://github.com/m-bain/whisperX/issues/639

Useful video:
- https://www.youtube.com/watch?v=zY-8Sr-FzIw

## Speaker diarization: pyannote Community-1

Project:
- https://github.com/pyannote/pyannote-audio

Official H100 80GB benchmark (last updated 2025-09):

- AMI ~1h files: Community-1 **31 s per hour**
- DIHARD3 ~5min files: Community-1 **37 s per hour**

Approx. 45-minute extrapolation: **23-28 s on H100**.

Videos:
- https://www.youtube.com/watch?v=CtjDotATEI0
- https://www.youtube.com/watch?v=wDH2rvkjymY

Desktop GPU results must be measured locally; H100 is not representative of consumer hardware.

## Sound scout: YAMNet

TensorFlow tutorial:
- https://www.tensorflow.org/hub/tutorials/yamnet

Video:
- https://www.youtube.com/watch?v=DLVA10sb1iE

Embedded research reference on Raspberry Pi 2W:

- original model: ~450-600 ms per 1 s clip
- quantized/pruned TinyML version: ~180-220 ms per 1 s clip

Paper:
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12568035/

This proves that a YAMNet-class scout can run sub-real-time even on weak hardware, but it does **not** justify inventing a desktop-GPU episode time. Benchmark locally.

## Sound verifier: PANNs

Projects:
- https://github.com/qiuqiangkong/audioset_tagging_cnn
- https://github.com/qiuqiangkong/panns_inference

Demo videos:
- https://www.youtube.com/watch?v=QyFNIhRxFrY
- https://www.youtube.com/watch?v=7TEtDMzdLeY

PANNs provides 527-class AudioSet tagging / SED. No trustworthy modern end-to-end benchmark sufficiently similar to our windowing/batching setup was found. Keep it behind a scout and benchmark locally.

## Active speaker: LR-ASD first, TalkNet as comparison

LR-ASD:
- https://github.com/Junhua-Liao/LR-ASD
- DOI: https://doi.org/10.1007/s11263-025-02399-2

Published/repository accuracy:

- 0.84M parameters
- 0.51 GFLOPs
- 94.45% AVA validation mAP

TalkNet comparison from the Light-ASD literature:

- ~15.7M parameters
- ~1.5 GFLOPs for three-candidate frame convention
- ~92.3% AVA mAP

TalkNet:
- https://github.com/TaoRuijie/TalkNet-ASD
- demo: https://www.youtube.com/watch?v=a7rLzt2ZWk0

### End-to-end reality check

NVIDIA Maxine Active Speaker Detection NIM current performance reference:
- https://docs.nvidia.com/nim/maxine/active-speaker-detection/latest/performance-results.html

Single-stream examples:

- A10G: roughly 54-60 FPS depending on speaker count
- RTX 4090: roughly 72-77 FPS

At 25 fps, processing every frame of a 45-minute episode would therefore still take roughly 15-21 minutes on those reference systems. NVIDIA explicitly notes video extension/frame buffering adds processing time and memory.

Conclusion: **ASD must be run only on speech windows and with reused face tracks / reduced frame sampling where accuracy permits.** The LR-ASD network itself is small; face detection, tracking, decoding and buffering are likely to dominate.

## Music separation: Demucs

Project:
- https://github.com/facebookresearch/demucs

2026 Apple M4 benchmark reference:
- https://stemsplitter.github.io/research/model-comparison/

Per 7-second clip:

- HTDemucs base: ~1.8 s
- HTDemucs FT: ~6.4 s

Straight 45-minute extrapolations are ~11.6 min and ~41.1 min respectively. Never run source separation over a full TV episode by default.

Video:
- https://www.youtube.com/watch?v=BttaeQaO80E

## Music analysis: Essentia

Project/docs:
- https://essentia.upf.edu/
- https://github.com/MTG/essentia

Essentia is C++-based, optimized for computational speed and supports streaming / real-time analysis. There is no useful single generic runtime because costs vary drastically by chosen descriptors/models.

Tutorial video:
- https://www.youtube.com/watch?v=6e1_6_UCzRw

## ffmpeg, voiceprints, fusion and export

No universal external time should be assigned:

- ffmpeg extraction is dominated by codec/container/storage and whether decoding/resampling is needed
- voiceprint cosine matching is tiny compared with model inference but depends on number of identities/embeddings
- JSON/SRT/ASS export is normally negligible

Instrument these locally and record median/p95 timing per episode.

## Target architecture and timing policy

Do not sum every standalone benchmark. Run independent branches concurrently and gate expensive work:

```text
                     +--> fast ASR ------------------+
                     +--> diarization ---------------+
media decode/cache --+--> sound scout -> verifier ---+--> fusion -> SRT/ASS
                     +--> sparse text detector -------+
                     +--> speech-only ASD ------------+
                     +--> selected music -> Demucs ---+
```

Recommended initial video sampling policy:

- text scout: scene cuts + 0.5 fps periodic baseline; temporarily raise to 2-5 fps around a newly detected text track
- OCR recognition: only new/changed crops
- ASD: only speech windows; reuse face tracks
- Demucs: only vocal-music windows where lyrics matter

The local benchmark harness should report for every provider:

- cold start
- warm total time
- RTF or FPS
- preprocessing / inference / postprocessing split
- peak VRAM/RAM
- number of input windows/frames actually processed
- cache hit rate
- p50/p95 episode wall-clock time

That local benchmark is the authority for future optimization decisions.