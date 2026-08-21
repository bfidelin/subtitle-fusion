# Performance references

Last verified: **2026-08-21**.

These numbers are reference measurements, not promises. Hardware, precision, batching, decoding, model loading and language all matter. Local benchmark results override projections.

## Consolidated reference matrix

| Stage | Reference measurement | Approx. 45-minute projection | Caveat |
|---|---:|---:|---|
| faster-whisper large-v2 FP16 batch=8 | 17 s / 13 min, RTX 3070 Ti | ~59 s | transcription only |
| faster-whisper large-v2 INT8 batch=8 | 16 s / 13 min, RTX 3070 Ti | ~55 s | transcription only |
| WhisperX large-v3 + alignment | 15.51 s / 5.4 min, T4 | ~2m09 | warm third-party benchmark |
| WhisperX large-v3 + alignment | ~9.5 s / 5.4 min, A10G/L4 | ~1m19 | warm third-party benchmark |
| pyannote Community-1 | 31–37 s / hour, H100 | ~23–28 s | H100 is not consumer hardware |
| PP-OCRv5_mobile_det | 6.36 ms/image, T4 high-performance | ~9 s at 0.5 fps sampling | inference only |
| PP-OCRv5_mobile_det | 28.15 ms/image, Xeon high-performance | ~38 s at 0.5 fps | inference only |
| PP-OCRv6_tiny_det | 0.43M params / 1.9 MB | local benchmark required | published timing uses different A100 setup |
| OpenVINO horizontal-text-detection-0001 | ~25.6 FPS official async demo | ~53 s at 0.5 fps | client/server demo, horizontal text |
| full PP-OCRv5 mobile OCR pipeline | ~0.62 s/image, V100 | too slow per frame | detection+recognition; use crops only |
| LR-ASD | 0.84M params / 0.51 GFLOPs / ~94.45% AVA mAP | model-only | face detection/tracking dominates full pipeline |
| NVIDIA end-to-end ASD | ~54–60 FPS A10G | ~19–21 min at full 25 fps | proves ASD must be sparse |
| NVIDIA end-to-end ASD | ~72–77 FPS RTX 4090 | ~15 min at full 25 fps | full video path |
| HTDemucs base | ~1.8 s / 7 s, Apple M4 | ~11m34 | selected music windows only |
| HTDemucs FT | ~6.4 s / 7 s, Apple M4 | ~41m09 | never full episode by default |
| ffsubsync | usually ~20–30 s/video | n/a | raw audio extraction is dominant |
| Alass | 10–20 s extraction + 5–10 s alignment | n/a | reference implementation/environment |

## Sources

### ASR / diarization
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- WhisperX: https://github.com/m-bain/whisperX
- additional WhisperX benchmark: https://github.com/Ziyang-Liao/WhisperX
- pyannote: https://github.com/pyannote/pyannote-audio

Useful videos:
- faster-whisper install/CPU-GPU benchmark: https://www.youtube.com/watch?v=Kyc0AgMIBSU
- WhisperX speaker/timestamp demo: https://www.youtube.com/watch?v=zY-8Sr-FzIw
- pyannote talk: https://www.youtube.com/watch?v=CtjDotATEI0

### Audio events/music
- YAMNet: https://www.tensorflow.org/hub/tutorials/yamnet
- YAMNet video: https://www.youtube.com/watch?v=DLVA10sb1iE
- PANNs: https://github.com/qiuqiangkong/audioset_tagging_cnn
- PANNs inference: https://github.com/qiuqiangkong/panns_inference
- PANNs demos: https://www.youtube.com/watch?v=QyFNIhRxFrY and https://www.youtube.com/watch?v=7TEtDMzdLeY
- Demucs official maintained fork: https://github.com/adefossez/demucs
- legacy Meta repo (archived/read-only since 2025): https://github.com/facebookresearch/demucs
- Demucs video: https://www.youtube.com/watch?v=BttaeQaO80E
- Essentia: https://essentia.upf.edu/ and https://github.com/MTG/essentia

Demucs note (verified 2026-08-21): `adefossez/demucs` is the official repository to follow after Alexandre Défossez left Meta. It is still **Demucs v4 / Hybrid Transformer Demucs**, not a new v5 release. The maintainer states that the project receives important fixes but is not under active feature development. For our use case, `htdemucs` remains the first model to benchmark and `htdemucs_ft` remains an optional higher-cost quality escalation. Run source separation only on selected vocal/music windows.

### OCR / text detection
- PaddleOCR detector docs: https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_detection.en.md
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- OpenVINO horizontal detector: https://docs.openvino.ai/2023.3/omz_models_model_horizontal_text_detection_0001.html
- OpenVINO real-time demo: https://docs.openvino.ai/2024/openvino-workflow/model-server/ovms_demo_horizontal_text_detection.html
- OpenVINO text recognizer: https://docs.openvino.ai/2023.3/omz_models_model_text_recognition_0014.html

A 45-minute episode at 25 fps contains **67,500 frames**. With a 0.5 fps periodic baseline there are only **1,350** periodic frames before scene-cut/adaptive samples. That is why detection + tracking + crop-cache is mandatory.

## Video-text policy

```text
scene cuts + 0.5 fps baseline
  -> cheap detector
  -> no boxes: stop
  -> boxes: track + perceptual hash
  -> unchanged crop: reuse OCR
  -> changed/new crop: recognize
  -> temporal vote + confidence
```

Temporarily raise sampling to 2–5 fps around newly appearing text, then drop back down after the track stabilizes/disappears.

## Active speaker

- LR-ASD: https://github.com/Junhua-Liao/LR-ASD
- TalkNet: https://github.com/TaoRuijie/TalkNet-ASD
- TalkNet demo: https://www.youtube.com/watch?v=a7rLzt2ZWk0
- NVIDIA end-to-end ASD performance: https://docs.nvidia.com/nim/maxine/active-speaker-detection/latest/performance-results.html

Use ASD only during speech windows, reuse face tracks and reset/refresh intelligently at shot changes.

## Synchronization prior art

### ffsubsync
- https://github.com/smacke/ffsubsync
- FFT-based global offset from 10 ms speech/non-speech signals
- typical 20–30 s/video; under a second if a synchronized SRT reference avoids audio extraction
- 2026 multi-segment sparse sync, fused VAD, quality gates, PGS reference, single-pass embedded subtitle extraction

### Alass
- https://github.com/kaegi/alass
- handles constant offsets, frame-rate differences and piecewise splits from ads/director cuts
- reports roughly 10–20 s audio extraction + 5–10 s alignment

### Subtitle Edit
- https://github.com/SubtitleEdit/subtitleedit
- waveform/spectrogram, shot detection, 380+ formats, OCR, ASR, batch operations, deterministic common-error fixes
- current 2026 work includes shot-change snap/extend tools and separate CPS/WPM visibility

### stable-ts
- https://github.com/jianfch/stable-ts
- useful prior art for post-ASR regrouping by punctuation/silence/gaps and bounded timing adjustment
- borrow principles; do not make it a required dependency solely for segmentation

## Target budget

For a warm 45-minute TV episode:
- fast enriched mode: **~1.5–3 minutes** target
- rich mode with sparse OCR/visual analysis: **~2–4 minutes** target

These are engineering objectives. `output.benchmark.json` will become the authority once the harness is implemented.
