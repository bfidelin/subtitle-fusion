# Fast scout + selective review architecture

The main performance principle of `subtitle-fusion` is:

> Do not run the most expensive model on the whole episode. Use very cheap scouts to find uncertainty, then spend compute only on the difficult windows.

The target use case is a 40–50 minute TV episode where the first ASR pass is already very fast. Quality improvements must preserve that speed by making expensive work sparse and local.

## Design goals

- keep the whole-episode pass cheap and parallel
- preserve word timestamps and ASR confidence
- detect text on screen without OCR-ing every frame at full quality
- detect music, singing and important sound events separately from dialogue
- re-run ASR only around suspicious words or segments
- use OCR, IMDb/title context and previous validated names as evidence
- separate ASR confidence, translation confidence and contextual confidence
- never let the Netflix formatter invent, truncate or silently paraphrase dialogue
- keep providers/backend implementations swappable

## Pipeline overview

```text
VIDEO + AUDIO
    |
    +----------------------+----------------------+----------------------+
    |                      |                      |                      |
    v                      v                      v                      v
cheap ASR scout       text detector         audio-event scout      shot detector
(Moonshine Tiny       (RapidOCR/             (YAMNet-like)          (FFmpeg/OpenCV)
 or similar)           PP-OCR mobile)
    |                      |                      |
    +----------------------+----------------------+----------------------+
                                   |
                                   v
                         FAST WHOLE-EPISODE PASS
                                   |
                                   v
                           Faster-Whisper ASR
                     timestamps + word confidence
                                   |
                                   v
                           CONFIDENCE ROUTER
                                   |
              +--------------------+--------------------+
              |                                         |
              v                                         v
         confidence OK                           suspicious window
         keep result                              crop 4–10 seconds
                                                        |
                                                        v
                                             selective re-evaluation
                                              - stronger ASR / beam
                                              - OCR recognition
                                              - nearby dialogue
                                              - IMDb/glossary
                                              - validated names
                                              - speaker context
                                              - phonetic candidates
                                                        |
                                                        v
                                              contextual reviewer
                                                        |
                                                        v
                                      grammar/spelling/translation QA
                                                        |
                                                        v
                                               Netflix / SDH pass
                                                        |
                                                        v
                                              SRT + ASS + debug JSON
```

## Level 0: ultra-cheap scouts

These components should be able to process the full episode at low cost. They do not need to be authoritative; their purpose is to locate interesting regions and provide independent evidence.

### ASR scout

Preferred direction:

- `Moonshine Tiny` / `Moonshine Tiny Streaming` as a modern very-small ASR scout
- keep `PocketSphinx` only as an optional legacy/minimal backend for constrained cases
- do **not** replace Faster-Whisper with the scout

The scout is useful because disagreement is itself a signal. Example:

```text
Scout:   "Muriel closed the door"
Whisper: "Murel closed the door"   confidence=0.41
IMDb:    Muriel
OCR:     MURIEL

=> strong reason to re-evaluate/correct the name
```

A cheap secondary transcription can therefore improve routing even when its own transcript is not good enough for final output.

### Fast text detection

Do not OCR every video frame at full resolution.

Recommended strategy:

1. sample frames at a low frequency, for example every 0.5–1.0 s
2. run only fast text detection first
3. track/reuse detected regions while they remain stable
4. run recognition only on new or changed regions
5. escalate to a more accurate OCR model only for relevant or uncertain text

Suggested provider family:

- RapidOCR + ONNX Runtime as a lightweight/default detector-recognizer backend
- PP-OCR mobile models as an alternative or accuracy escalation path
- OpenVINO backend where Intel hardware makes it useful

High-value OCR targets include:

- character/name captions
- phone/SMS/chat text
- signs and locations
- title cards
- documents that affect the plot
- credits when they help identify names/music

### Audio-event scout

Use a broad, inexpensive AudioSet/YAMNet-like classifier to identify candidate windows for:

- music
- singing/vocal music
- door slams
- footsteps
- alarms
- gunshots
- crowds
- thunder
- other plot-relevant events

This classifier is a router, not the final SDH caption generator.

### Shot detection

Use cheap scene/shot detection from FFmpeg/OpenCV or an equivalent backend. Shot boundaries later help Netflix-style subtitle timing and prevent badly hanging captions across cuts.

## Level 1: normal whole-episode ASR

The current fast Faster-Whisper path remains the primary transcription pass.

Required outputs:

- segment start/end timestamps
- word timestamps where available
- word confidence/probability
- language
- optional no-speech probability
- optional alternative candidates when inexpensive

This is the transcript that should be accepted directly for the majority of the episode.

## Confidence router

Confidence must control **compute cost**, not just display a score.

Initial policy direction:

```text
very high confidence
    -> accept directly

medium confidence
    -> cheap contextual checks only

low confidence
    -> crop local audio + second ASR + OCR/name evidence

very low confidence / conflicting evidence
    -> stronger ASR + wider context + reviewer
```

Example starting thresholds (to calibrate on real episodes, not hard-code as universal truth):

```text
> 0.90       accept unless another signal conflicts
0.70–0.90    lightweight context/name check
0.45–0.70    selective re-ASR + OCR/context
< 0.45       strong re-evaluation/reviewer
```

Other triggers must be able to escalate a segment even when ASR confidence looks good:

- proper-noun candidate not in glossary
- disagreement between scout ASR and primary ASR
- OCR evidence conflicts with ASR
- grammar/spelling anomaly
- improbable sentence in local dialogue context
- language switch
- overlapping speakers
- singing/music contamination
- named entity seen elsewhere with a different spelling

## Selective re-ASR

Never re-run a large ASR model over the whole episode merely because a few segments are poor.

For a suspicious segment, extract a local window such as:

```text
segment start - 2 s ... segment end + 2 s
```

or widen to roughly 4–10 seconds when context is needed.

Possible escalation knobs:

- larger/more accurate Whisper model
- higher beam/best-of
- alternate temperature/decoding settings
- VAD-aware crop boundaries
- isolated dialogue stem if music is masking speech
- language hint
- initial prompt containing validated character/place names

Store all hypotheses in debug metadata before choosing the final text.

## Contextual review

The reviewer should reason over a small local context, not the entire episode transcript unless necessary.

Recommended context package:

- target audio window
- primary ASR text and confidence
- scout ASR hypothesis
- 2–3 previous subtitle events
- 2–3 following subtitle events
- speaker ID / diarization result
- OCR hits around the same timestamp
- current title/season/episode
- IMDb character/actor candidates
- recurring show glossary
- names already validated earlier in the episode
- phonetic alternatives

The reviewer may correct spelling, grammar, punctuation and translation, but must preserve meaning and keep the raw ASR evidence untouched.

## Separate confidence dimensions

Avoid one opaque "magic confidence" score. Keep independent evidence scores where possible:

```text
asr_confidence
scout_agreement
ocr_confidence
proper_noun_confidence
context_confidence
translation_confidence
linguistic_qa_confidence
final_confidence
```

`final_confidence` can be a routing/decision score, but the underlying components must remain visible in `output.debug.json` so a correction is explainable.

## Proper names and OCR

Proper names deserve special handling because a one-token ASR error is common but very visible in subtitles.

Evidence priority remains:

1. explicit on-screen OCR
2. title/episode-restricted character candidates
3. names already validated in the current episode/show glossary
4. dialogue context
5. actor/face hint
6. phonetic similarity

Never translate a proper name merely to improve linguistic fluency. Preserve approved spelling, accents and diacritics.

## Music and sung lyrics

Music handling is also selective.

```text
music detected
    |
    v
singing/vocal likely?
    | no ------------------> concise SDH music label if relevant
    |
   yes
    |
    v
crop only the music window
    |
    v
optional source separation
(Demucs vocals/instrumental)
    |
    v
ASR on isolated vocals
    |
    v
lyrics confidence + track metadata/context
    |
    +--> intelligible + relevant -> subtitle lyrics
    |
    +--> uncertain/not relevant -> music label only
```

Do not run Demucs across an entire episode by default. Run it only on musical windows where vocal isolation is likely to improve lyric transcription or dialogue recovery.

Intel/OpenVINO prior art is useful here: the OpenVINO AI plugins for Audacity demonstrate both Whisper-oriented transcription and Demucs-based music separation. The project should copy the architectural idea, not bind itself to Intel hardware.

## Backend strategy

The architecture must be provider/backend agnostic.

Possible adapters:

```text
ASR_PRIMARY
- faster-whisper CUDA
- whisper.cpp
- OpenVINO Whisper

ASR_SCOUT
- Moonshine Tiny / Streaming
- PocketSphinx (optional legacy/minimal)

OCR_FAST
- RapidOCR ONNX Runtime
- PP-OCR mobile
- OpenVINO

AUDIO_EVENTS
- YAMNet / AudioSet family

SOURCE_SEPARATION
- Demucs CUDA
- OpenVINO Demucs

SHOT_DETECTION
- FFmpeg
- OpenCV
```

On an NVIDIA machine, CUDA will often be the preferred heavy-compute backend. OpenVINO remains valuable as an Intel adapter and as implementation prior art.

## Parallelism

The first-stage scouts should run concurrently where practical because they inspect independent modalities.

Conceptually:

```text
                   +-> ASR scout --------+
video/audio input -+-> OCR/text detect ---+-> evidence timeline
                   +-> audio events ------+
                   +-> shot detect -------+
```

The evidence timeline then feeds the confidence router and selective second pass.

Avoid parallelizing multiple large GPU jobs blindly if that causes contention; the scheduler should distinguish cheap CPU/ONNX work from heavy GPU escalation.

## Performance target

The performance objective is not "every stage is fast". It is:

> 90–95% of the episode should finish on the cheap/normal path; expensive work should be concentrated on the small fraction that is actually difficult.

The exact percentages must be measured on real episodes. Add profiling for:

- real-time factor by stage
- number/percentage of segments escalated
- seconds of audio reprocessed
- OCR frames/regions processed
- Demucs seconds processed
- GPU/CPU time per provider
- quality gain per escalation level

## Implementation order

1. add an evidence timeline and router data model
2. wire real Faster-Whisper word confidence into the router
3. add local audio crop + selective re-ASR
4. add fast OCR detection and region-based recognition
5. add show/episode proper-name glossary persistence
6. add scout ASR adapter (Moonshine first)
7. add audio-event/music/singing routing
8. add selective Demucs + vocal ASR
9. add grammar/spelling/translation QA reviewer
10. add shot-aware Netflix timing
11. profile and calibrate thresholds on real episodes

## References / prior art

- Moonshine: https://github.com/moonshine-ai/moonshine
- PocketSphinx: https://github.com/cmusphinx/pocketsphinx
- RapidOCR: https://github.com/RapidAI/RapidOCR
- PaddleOCR / PP-OCR: https://github.com/PaddlePaddle/PaddleOCR
- YAMNet: https://www.tensorflow.org/hub/tutorials/yamnet
- Demucs: https://github.com/facebookresearch/demucs
- Intel OpenVINO AI plugins for Audacity: https://github.com/intel/openvino-plugins-ai-audacity

These are implementation references, not mandatory dependencies. Provider interfaces should allow replacements without changing subtitle semantics.
