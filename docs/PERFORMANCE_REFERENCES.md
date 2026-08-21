# Performance references and fast-path design

This document collects external references, videos, and benchmark numbers used to guide the performance architecture of `subtitle-fusion`.

The numbers below are **reference measurements, not promises**. Hardware, model precision, batch size, decoding, preprocessing and cold-start/model-loading time can change results significantly. Always measure the complete local pipeline on representative episodes.

## Core principle

Do not run the expensive model everywhere.

Use a fast first-pass detector to decide where more expensive analysis is useful:

```text
fast scout / detector
        |
        +-- confidence high / nothing relevant --> skip
        |
        +-- candidate / uncertain window --------> expensive recognizer / verifier
```

For a 45-minute episode this means:

- fast ASR first; re-align/re-evaluate only uncertain dialogue when possible
- fast sound classification first; heavier audio analysis only on candidate windows
- fast **text detection** first; OCR recognition only on detected text regions
- active-speaker analysis only around speech and preferably at sparse frame rates
- Demucs only on music windows where lyric recovery is useful

---

## ASR: faster-whisper

Project:
- https://github.com/SYSTRAN/faster-whisper

Official benchmark reference:
- https://github.com/SYSTRAN/faster-whisper#benchmark

Useful video:
- Faster-Whisper: A Beginners Installation Guide (includes CPU/GPU benchmark)
- https://www.youtube.com/watch?v=Kyc0AgMIBSU

Published reference benchmark on RTX 3070 Ti 8 GB, large-v2, 13 minutes of audio:

- FP16 batch 8: ~17 s
- INT8 batch 8: ~16 s

That scales roughly to around one minute for 45 minutes of audio if throughput remains similar, which is consistent with the current local target.

Preferred design: keep the already-fast ASR path as the main transcription engine and do not automatically replace it with a slower end-to-end path solely to obtain extra metadata.

---

## Alignment / enriched ASR: WhisperX

Main project:
- https://github.com/m-bain/whisperX

Additional benchmark implementation/reference used during research:
- https://github.com/Ziyang-Liao/WhisperX

Useful video:
- Best FREE Speech to Text AI - WhisperX - w/ Speaker Detection
- https://www.youtube.com/watch?v=zY-8Sr-FzIw

Reported warm benchmark for transcription + alignment on a 5.4-minute file:

- NVIDIA T4: ~15.5 s
- NVIDIA A10G: ~9.5 s
- NVIDIA L4: ~9.4 s

Preferred design: if faster-whisper already produces a good transcript, reuse it and reserve WhisperX alignment / reprocessing for timing refinement and difficult windows instead of blindly retranscribing everything.

---

## Speaker diarization: pyannote Community-1

Project:
- https://github.com/pyannote/pyannote-audio

Official benchmark section:
- https://github.com/pyannote/pyannote-audio#benchmark

Videos listed by the pyannote project:
- Speaker diarization, a love/loss story (JSALT 2025)
- https://www.youtube.com/watch?v=CtjDotATEI0
- Speaker segmentation model (Interspeech 2021)
- https://www.youtube.com/watch?v=wDH2rvkjymY

Official self-hosted H100 reference:

- Community-1: ~31 s per hour on AMI
- Community-1: ~37 s per hour on DIHARD3

Desktop GPUs will be slower, so local measurement matters.

---

## Sound-event scout: YAMNet

Model/documentation:
- https://www.tensorflow.org/hub/tutorials/yamnet

Useful video:
- Sound classification with YAMNet
- https://www.youtube.com/watch?v=DLVA10sb1iE

Embedded reference measurement used during research:
- optimized YAMNet-like TinyML deployment on Raspberry Pi 2W: ~180-220 ms per 1-second clip
- baseline reported in the same study: ~450-600 ms per 1-second clip
- paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC12568035/

Preferred design: use YAMNet (or another tiny AudioSet classifier) as a cheap scout and escalate ambiguous / important windows to PANNs or another stronger detector.

---

## Sound-event verification: PANNs

Project:
- https://github.com/qiuqiangkong/audioset_tagging_cnn

Inference helper:
- https://github.com/qiuqiangkong/panns_inference

Demo videos:
- https://www.youtube.com/watch?v=QyFNIhRxFrY
- https://www.youtube.com/watch?v=7TEtDMzdLeY

PANNs provides AudioSet-style sound classes and temporal sound-event detection. No sufficiently trustworthy modern end-to-end GPU timing benchmark was found during this research pass, so **do not put a made-up episode timing in the budget**. Benchmark it locally with the actual window size and batching used by `subtitle-fusion`.

---

# Fast video text detection: preferred OCR architecture

## Why full OCR on video is the wrong first pass

Running a recognizer on every video frame is wasteful. At 25 fps, a 45-minute episode contains about 67,500 frames.

The pipeline should separate two tasks:

1. **text detection**: is there text, and where is it?
2. **text recognition**: what do the detected pixels say?

Recognition should only run on the small crops returned by the detector, and usually only when a crop first appears or changes.

## Preferred detector: Intel/OpenVINO `horizontal-text-detection-0001`

Model documentation:
- https://docs.openvino.ai/2023.3/omz_models_model_horizontal_text_detection_0001.html

Real-time video demo:
- https://docs.openvino.ai/2024/openvino-workflow/model-server/ovms_demo_horizontal_text_detection.html

OpenVINO text-detection demo:
- https://docs.openvino.ai/2023.3/omz_demos_text_detection_demo_cpp.html

Current OpenVINO verified-model list:
- https://docs.openvino.ai/2026/documentation/compatibility-and-support/supported-models.html

OCR notebook combining the fast detector with `text-recognition-0014`:
- https://docs.openvino.ai/2024/notebooks/optical-character-recognition-with-output.html

Open Model Zoo:
- https://github.com/openvinotoolkit/open_model_zoo

### Why it is interesting

`horizontal-text-detection-0001` is a FCOS detector with a MobileNetV2-like backbone intended for mostly horizontal scene text.

Reference model complexity:

- ~7.78 GFLOPs
- ~2.26 M parameters
- ICDAR2013 F-measure: 88.45%

For comparison, OpenVINO reports approximately:

- `text-detection-0004`: 23.3 GFLOPs / 4.33 M params
- `text-detection-0003`: 51.3 GFLOPs / 6.75 M params

OpenVINO explicitly describes `horizontal-text-detection-0001` as much faster than the more general detectors.

### Real-time reference

Intel's OVMS demo accepts a camera or video file and shows multiple asynchronous request threads around:

- ~25.6-25.7 average FPS per reported stream/thread in the example
- ~130-141 ms average request latency

The demo uses 704x704 input and parallel requests. Treat this as a reference setup, not a guarantee on our hardware.

### Device support

The model is currently verified by OpenVINO on:

- CPU
- Intel GPU
- Intel NPU for supported precisions/configurations

This makes it especially attractive as a scout because it does not have to consume the NVIDIA GPU that Whisper/pyannote may already be using.

## Recognition after detection

OpenVINO example recognizer:
- `text-recognition-0014`
- https://docs.openvino.ai/2023.3/omz_models_model_text_recognition_0014.html

The recognizer should receive only tight crops returned by the detector.

Other recognizers can remain pluggable:

- PaddleOCR / PP-OCR
- RapidOCR
- EasyOCR
- Tesseract only as a compatibility fallback, not the preferred video path

## Fallback for rotated / difficult text

`horizontal-text-detection-0001` deliberately favors mostly horizontal text. That is ideal for:

- lower thirds
- signs shot mostly straight
- phone/computer UI
- captions inside the image
- names and location cards

For rotated/perspective-heavy text, escalate only those frames/crops to a general detector such as:

- OpenVINO `text-detection-0004`
- DBNet / Paddle text detector
- CRAFT

Do not run the general detector across the whole episode by default.

## Proposed video-text pipeline

```text
video decoder
   |
   +--> scene-change / periodic sparse sampler
           |
           v
 OpenVINO horizontal-text-detection-0001
           |
     no boxes --> stop
           |
           +--> track boxes across neighbouring frames
           |
           +--> perceptual hash / crop-change check
                     |
            unchanged --> reuse cached OCR
                     |
             changed/new --> recognize crop
                               |
                      text-recognition-0014
                      or Paddle/RapidOCR
                               |
                      confidence + temporal voting
                               |
                    OCRHit / proper-name evidence
```

### Important optimizations

- sample at scene cuts plus a low periodic rate instead of 25/30 fps
- once a text box is detected, track it for the next frames instead of redetecting everything
- hash/correlate the crop and do not re-OCR unchanged text
- OCR one or a few sharp/key frames from each stable text track
- use temporal voting across duplicate observations
- preserve raw OCR candidates and confidence
- only promote text into subtitle correction when the evidence is strong
- use IMDb/dialogue context for proper names after OCR, not instead of OCR

This should make OCR a **small sparse side-pass**, not a multi-minute full-video bottleneck.

---

## Active speaker: TalkNet vs LR-ASD

TalkNet project:
- https://github.com/TaoRuijie/TalkNet-ASD

TalkNet demo video:
- https://www.youtube.com/watch?v=a7rLzt2ZWk0

LR-ASD project:
- https://github.com/Junhua-Liao/LR-ASD

LR-ASD paper:
- https://doi.org/10.1007/s11263-025-02399-2

Recent comparison reports:

- TalkNet: ~15.7 M params, ~1.5 GFLOPs, ~92.3% AVA mAP
- LR-ASD: ~0.84 M params, ~0.51 GFLOPs, ~94.5% AVA mAP

For this project LR-ASD is therefore the preferred candidate to benchmark before adopting TalkNet.

Important: model FLOPs are not the whole pipeline. Face detection, tracking, frame decoding and buffering can dominate runtime.

NVIDIA's current end-to-end Active Speaker Detection NIM reference:
- https://docs.nvidia.com/nim/maxine/active-speaker-detection/latest/performance-results.html

Example single-stream figures include roughly 58-60 FPS on A10G and ~72+ FPS on RTX 4090 depending on speaker count. NVIDIA also notes that video extension operations increase processing time and memory use.

Preferred design: run ASD only on speech windows, use reduced/smart frame sampling where accuracy allows it, and reuse face tracks.

---

## Music source separation: Demucs

Project:
- https://github.com/facebookresearch/demucs

Useful video:
- How to use Hybrid Demucs V3/V4
- https://www.youtube.com/watch?v=BttaeQaO80E

Demucs is valuable for recovering vocals/lyrics from music but is too expensive to run blindly across a full episode. Trigger it only on vocal-music windows that are relevant to subtitle generation.

---

## Music analysis: Essentia

Project/documentation:
- https://essentia.upf.edu/
- https://github.com/MTG/essentia

Tutorial video:
- https://www.youtube.com/watch?v=6e1_6_UCzRw

Essentia is a C++ audio-analysis library with Python bindings and streaming capabilities. No sufficiently comparable current end-to-end episode benchmark was found during this research pass, so benchmark the exact algorithms selected rather than assigning a generic timing.

---

## Performance target for subtitle-fusion

The target is not "run every model on every sample". The target is a cascade:

```text
cheap scout -> candidate window -> stronger verifier -> fusion
```

For a 45-minute TV episode, aim for:

- transcription around or below the current ~1 minute baseline
- diarization in parallel with ASR
- sound analysis in parallel
- video text detection as a sparse OpenVINO side-pass
- OCR recognition only for new/changed text tracks
- active-speaker analysis only where speaker visibility matters
- source separation only on selected music windows

The final wall-clock time should be bounded mainly by the slowest parallel branch, not by the sum of every model's standalone runtime.
