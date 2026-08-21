# Fast scout + selective review architecture

The main performance principle of `subtitle-fusion` is:

> Do not run the most expensive model on the whole episode. Use very cheap scouts to find uncertainty, then spend compute only on the difficult windows.

The target use case is a 40–50 minute TV episode where the first ASR pass is already very fast. Quality improvements must preserve that speed by making expensive work sparse and local.

## Design goals

- keep the whole-episode pass cheap and parallel
- preserve word timestamps and ASR confidence
- make speaker diarization a first-class signal, not a late reviewer hint
- keep stable speaker IDs across the episode
- detect speaker changes and overlapping speech explicitly
- distinguish diarization (`SPEAKER_03`) from character identity (`Muriel`)
- detect text on screen without OCR-ing every frame at full quality
- detect music, singing and important sound events separately from dialogue
- re-run ASR only around suspicious words or segments
- use OCR, IMDb/title context and previous validated names as evidence
- separate ASR, diarization, speaker identity, translation and contextual confidence
- never let the Netflix formatter invent, truncate or silently paraphrase dialogue
- keep providers/backend implementations swappable

## Pipeline overview

```text
VIDEO + AUDIO
    |
    +----------------------+----------------------+----------------------+----------------------+
    |                      |                      |                      |                      |
    v                      v                      v                      v                      v
cheap ASR scout       text detector         audio-event scout      shot detector       diarization
(Moonshine Tiny       (RapidOCR/             (YAMNet-like)          (FFmpeg/OpenCV)     speaker turns
 or similar)           PP-OCR mobile)                                                     overlaps
    |                      |                      |                      |                  stable IDs
    +----------------------+----------------------+----------------------+----------------------+
                                               |
                                               v
                                     EVIDENCE TIMELINE
                                               |
                                               v
                                      Faster-Whisper ASR
                                timestamps + word confidence
                                               |
                                               v
                                      CONFIDENCE ROUTER
                                               |
                         +---------------------+---------------------+
                         |                                           |
                         v                                           v
                    confidence OK                             suspicious window
                    keep result                                crop 4–10 seconds
                                                                    |
                                                                    v
                                                         selective re-evaluation
                                                          - stronger ASR / beam
                                                          - OCR recognition
                                                          - nearby dialogue
                                                          - IMDb/glossary
                                                          - validated names
                                                          - speaker/overlap context
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

The evidence timeline is the central join point. ASR words, speaker turns, OCR hits, shot boundaries, music windows and sound events should all be timestamped so later stages can reason over the same local window.

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

## Diarization: first-class speaker timeline

Diarization runs alongside the whole-episode ASR path and contributes evidence before contextual review.

The core question is:

> **Who spoke when?**

It is deliberately separate from:

> **Which character is this speaker?**

The diarizer should produce stable episode-local IDs such as:

```text
00:01:12.200 --> 00:01:16.900  SPEAKER_01
00:01:17.000 --> 00:01:19.400  SPEAKER_02
00:01:19.100 --> 00:01:20.200  SPEAKER_01 + SPEAKER_02  overlap
```

Required evidence where available:

- speaker-turn start/end timestamps
- stable episode-local speaker ID
- speaker-change boundaries
- overlap regions
- diarization confidence/quality signal
- optional speaker embedding/reference ID for clustering

### Diarization is not character identification

Keep these concepts separate in the data model:

```text
speaker_id = SPEAKER_03
speaker_identity_candidate = Muriel
speaker_identity_confidence = 0.94
```

`SPEAKER_03` means only that the system believes the same voice appears in those regions. Mapping it to `Muriel` requires independent evidence such as:

1. visible/on-screen speaker context
2. OCR/name card evidence
3. dialogue context
4. title/episode character candidates
5. previously validated speaker-to-character mappings
6. optional face/actor hints

This prevents a diarization clustering error from silently becoming a wrong character name.

### Fast/slow policy for diarization

Apply the same selective-compute philosophy used elsewhere:

- run a fast whole-episode VAD/speaker-change/embedding path
- cluster speaker embeddings globally or in chunks
- keep stable speaker IDs for the episode
- only escalate ambiguous boundaries, overlaps or low-confidence turns
- avoid expensive re-diarization of clean single-speaker regions

Useful escalation triggers include:

- two voices overlap
- rapid turn-taking
- a speaker ID changes inside one grammatical utterance
- speaker identity conflicts with visible character evidence
- the same apparent character receives multiple speaker IDs
- diarization confidence is low near a subtitle boundary

### How diarization improves SDH

Diarization is essential for deciding whether a visible speaker label is needed.

Examples:

```text
SPEAKER_03 visible and obvious
-> no label needed

SPEAKER_03 off-screen, identity known as Muriel
-> [Muriel] Attends-moi !

SPEAKER_03 off-screen, identity not yet revealed
-> [voix féminine] Attends-moi !

SPEAKER_01 and SPEAKER_02 overlap
-> split/position dialogue or label speakers according to the output format/style rules
```

The renderer must remain spoiler-safe: a validated backend identity must not be displayed before the story has revealed that identity to the viewer.

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

ASR alignment should consume diarization boundaries when useful, especially around rapid speaker changes and overlaps, but the ASR text and speaker timeline remain independently inspectable evidence.

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
- low-confidence speaker boundary
- inconsistent speaker identity
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
- diarization-aware crop boundaries
- isolated dialogue stem if music is masking speech
- language hint
- initial prompt containing validated character/place names

For overlaps, the local review path may optionally separate voices/stems or rerun alignment with speaker boundaries rather than treating the mixed region as a normal single-speaker segment.

Store all hypotheses in debug metadata before choosing the final text.

## Contextual review

The reviewer should reason over a small local context, not the entire episode transcript unless necessary.

Recommended context package:

- target audio window
- primary ASR text and confidence
- scout ASR hypothesis
- 2–3 previous subtitle events
- 2–3 following subtitle events
- stable speaker ID
- diarization confidence
- overlap flags/timestamps
- candidate character identity and confidence
- OCR hits around the same timestamp
- current title/season/episode
- IMDb character/actor candidates
- recurring show glossary
- names already validated earlier in the episode
- previously validated speaker-to-character mappings
- phonetic alternatives

The reviewer may correct spelling, grammar, punctuation and translation, but must preserve meaning and keep the raw ASR evidence untouched.

## Separate confidence dimensions

Avoid one opaque "magic confidence" score. Keep independent evidence scores where possible:

```text
asr_confidence
scout_agreement
diarization_confidence
speaker_identity_confidence
ocr_confidence
proper_noun_confidence
context_confidence
translation_confidence
linguistic_qa_confidence
final_confidence
```

`final_confidence` can be a routing/decision score, but the underlying components must remain visible in `output.debug.json` so a correction is explainable.

A speaker identity must never be inferred solely because `diarization_confidence` is high. Those two scores answer different questions.

## Proper names and OCR

Proper names deserve special handling because a one-token ASR error is common but very visible in subtitles.

Evidence priority remains:

1. explicit on-screen OCR
2. title/episode-restricted character candidates
3. names already validated in the current episode/show glossary
4. dialogue context
5. validated speaker-to-character continuity
6. actor/face hint
7. phonetic similarity

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

Use `https://github.com/adefossez/demucs` as the canonical Demucs source. It is the official repository maintained after Alexandre Défossez left Meta. As of 2026-08-21 the model generation is still Demucs v4 / Hybrid Transformer Demucs; this repository transition is not a Demucs v5 release. The project is in maintenance mode with important fixes rather than active feature development. Benchmark `htdemucs` first; use `htdemucs_ft` only as a selected-window quality escalation when its extra cost is justified.

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

DIARIZATION
- interchangeable VAD / speaker embedding / clustering adapter
- optional stronger overlap/boundary refinement backend

OCR_FAST
- RapidOCR ONNX Runtime
- PP-OCR mobile
- OpenVINO

AUDIO_EVENTS
- YAMNet / AudioSet family

SOURCE_SEPARATION
- Demucs v4 / HTDemucs CUDA
- OpenVINO Demucs

SHOT_DETECTION
- FFmpeg
- OpenCV
```

On an NVIDIA machine, CUDA will often be the preferred heavy-compute backend. OpenVINO remains valuable as an Intel adapter and as implementation prior art.

## Parallelism

The first-stage scouts and diarization should run concurrently where practical because they inspect complementary signals.

Conceptually:

```text
                   +-> ASR scout --------+
                   +-> diarization -------+
video/audio input -+-> OCR/text detect ---+-> evidence timeline
                   +-> audio events ------+
                   +-> shot detect -------+
```

Diarization may share VAD/audio preprocessing with the ASR path to avoid decoding or resampling the same audio repeatedly.

The evidence timeline then feeds the confidence router and selective second pass.

Avoid parallelizing multiple large GPU jobs blindly if that causes contention; the scheduler should distinguish cheap CPU/ONNX work from heavy GPU escalation.

## Performance target

The performance objective is not "every stage is fast". It is:

> 90–95% of the episode should finish on the cheap/normal path; expensive work should be concentrated on the small fraction that is actually difficult.

The exact percentages must be measured on real episodes. Add profiling for:

- real-time factor by stage
- number/percentage of segments escalated
- seconds of audio reprocessed
- diarization runtime
- number of speaker turns and overlaps
- percentage of low-confidence speaker boundaries
- number of speaker identities resolved/changed
- OCR frames/regions processed
- Demucs seconds processed
- GPU/CPU time per provider
- quality gain per escalation level

## Implementation order

1. add an evidence timeline and router data model
2. wire real Faster-Whisper word confidence into the router
3. add first-class diarization turns, overlaps and stable speaker IDs to the evidence timeline
4. add local audio crop + selective re-ASR
5. add fast OCR detection and region-based recognition
6. add show/episode proper-name glossary persistence
7. add speaker-identity resolution separate from diarization
8. add scout ASR adapter (Moonshine first)
9. add audio-event/music/singing routing
10. add selective Demucs + vocal ASR
11. add grammar/spelling/translation QA reviewer
12. add shot-aware Netflix timing
13. profile and calibrate thresholds on real episodes

## References / prior art

- Moonshine: https://github.com/moonshine-ai/moonshine
- PocketSphinx: https://github.com/cmusphinx/pocketsphinx
- RapidOCR: https://github.com/RapidAI/RapidOCR
- PaddleOCR / PP-OCR: https://github.com/PaddlePaddle/PaddleOCR
- YAMNet: https://www.tensorflow.org/hub/tutorials/yamnet
- Demucs (official maintained fork): https://github.com/adefossez/demucs
- Demucs legacy Meta repository (archived): https://github.com/facebookresearch/demucs
- Intel OpenVINO AI plugins for Audacity: https://github.com/intel/openvino-plugins-ai-audacity

These are implementation references, not mandatory dependencies. Provider interfaces should allow replacements without changing subtitle semantics.
