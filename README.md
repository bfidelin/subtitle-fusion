# subtitle-fusion

Production-oriented Python project to generate enriched subtitles from video by combining:

- ASR with word timestamps and confidence
- a very-fast scout layer to locate difficult regions before expensive processing
- first-class speaker diarization with stable episode-local speaker IDs and overlap detection
- speaker-to-character identity resolution kept separate from diarization
- OCR from video frames
- IMDb context for title, cast, and character names
- optional actor/face hints
- rule-based fusion and SDH output
- audio-event, music, singing, lyric and track-recognition hooks
- Netflix-style French (France) formatting and compliance checks

## Planned outputs

- `output.debug.json`
- `output.srt`
- `output.ass`
- `output.netflix-report.json`

## Architecture principle

The main performance rule is:

> Run cheap scouts on the whole episode, then spend compute only on uncertain or interesting windows.

The fast path should handle most of an episode with the existing fast Faster-Whisper workflow. A confidence router escalates only suspicious segments to local re-ASR, OCR, source separation, diarization refinement or contextual review.

Detailed design: `docs/FAST_SCOUT_PIPELINE.md`.

Typical flow:

```text
video/audio
   |
   +-> tiny ASR scout --------+
   +-> diarization -----------+
   +-> fast text detection ---+-> evidence timeline
   +-> audio/music scout -----+
   +-> shot detection --------+
                               |
                               v
                         Faster-Whisper
                               |
                        confidence router
                         /             \
                    accept          local review
                                      |
                 re-ASR + OCR + speaker + names/context
                                      |
                         linguistic/translation QA
                                      |
                             Netflix / SDH output
```

Potential provider families are intentionally adapters rather than hard dependencies:

- scout ASR: Moonshine Tiny / Tiny Streaming; optional PocketSphinx legacy backend
- primary ASR: Faster-Whisper, whisper.cpp/OpenVINO alternatives
- diarization: interchangeable VAD / speaker embedding / clustering / overlap-refinement adapters
- fast OCR: RapidOCR/ONNX Runtime, PP-OCR mobile, OpenVINO adapters
- audio events/music/singing: YAMNet/AudioSet-like classifiers
- source separation: Demucs CUDA or OpenVINO Demucs
- shot detection: FFmpeg/OpenCV

## Repository layout

```text
subtitle_fusion/
├─ pyproject.toml
├─ README.md
├─ AGENTS.md
├─ .env.example
├─ config/
│  ├─ settings.yaml
│  ├─ scoring.yaml
│  ├─ style_rules.yaml
│  └─ audio_analysis.yaml
├─ docs/
│  ├─ FAST_SCOUT_PIPELINE.md
│  ├─ SDH_STYLE_GUIDE.md
│  ├─ NETFLIX_FR_STYLE.md
│  └─ AUDIO_EVENTS_AND_MUSIC.md
├─ src/
│  ├─ main.py
│  ├─ pipeline.py
│  ├─ models.py
│  ├─ scoring.py
│  ├─ imdb_index.py
│  ├─ fusion.py
│  ├─ netflix_style.py
│  ├─ exporters.py
│  ├─ audio_music.py
│  └─ track_recognition.py
└─ tests/
   ├─ test_scoring.py
   ├─ test_fusion.py
   ├─ test_imdb_index.py
   └─ test_netflix_style.py
```

## Core design

The pipeline should only auto-correct uncertain segments, using evidence in this order:

1. explicit OCR text on screen
2. IMDb candidates restricted to the current title/episode
3. names already validated in the show/episode glossary
4. dialogue context
5. validated speaker-to-character continuity
6. actor/face hint
7. phonetic similarity

Raw ASR text must always be preserved alongside corrected text.

A second small ASR scout can provide an independent hypothesis. Disagreement between the scout and Faster-Whisper is itself a useful escalation signal, especially for proper names.

## Diarization and speaker identity

Diarization is a first-class branch of the pipeline, running alongside ASR/OCR/audio-event analysis and feeding the shared evidence timeline.

It answers:

> **Who spoke when?**

It does **not** by itself answer:

> **Which character is speaking?**

Keep those values separate:

```text
speaker_id = SPEAKER_03
speaker_identity_candidate = Muriel
speaker_identity_confidence = 0.94
```

The diarization layer should provide, where available:

- speaker-turn start/end timestamps
- stable episode-local `SPEAKER_xx` IDs
- speaker-change boundaries
- overlap regions
- diarization confidence/quality signals
- optional speaker embeddings/reference IDs for clustering

Character identity is then resolved from independent evidence such as OCR/name cards, visible context, IMDb/title candidates, dialogue context, previously validated speaker mappings and optional face hints.

This separation is important: a confident voice cluster must not automatically become a confident character name.

The same fast/slow policy applies to diarization:

- whole-episode VAD/speaker changes/embeddings should stay cheap
- clean single-speaker regions should be accepted directly
- only ambiguous boundaries, overlaps or identity conflicts should receive expensive refinement

Diarization also drives SDH speaker rendering. Examples:

```text
speaker visible and obvious
-> no speaker label

off-screen speaker, identity known and already revealed
-> [Muriel] Attends-moi !

off-screen speaker, identity not yet revealed
-> [voix féminine] Attends-moi !

overlapping speakers
-> split/label/position according to SDH/output rules
```

## Confidence-driven compute

Confidence is not only a quality metric; it controls how much processing a segment receives.

Initial routing direction, to be calibrated on real episodes:

```text
> 0.90       accept unless another signal conflicts
0.70–0.90    lightweight context/name check
0.45–0.70    selective re-ASR + OCR/context
< 0.45       stronger local re-evaluation + reviewer
```

Other signals can force review regardless of ASR confidence:

- scout ASR disagreement
- OCR conflict
- unknown/probable proper noun
- grammar or spelling anomaly
- overlapping speakers
- low-confidence speaker boundary
- inconsistent speaker identity
- language switch
- music/singing contamination
- inconsistent spelling of a previously validated name

Do not collapse all evidence into one opaque score. Planned/debug confidence fields include:

- `asr_confidence`
- `scout_agreement`
- `diarization_confidence`
- `speaker_identity_confidence`
- `ocr_confidence`
- `proper_noun_confidence`
- `context_confidence`
- `translation_confidence`
- `linguistic_qa_confidence`
- `final_confidence`

## Selective re-ASR and contextual review

For a suspicious segment, crop only the local audio window, typically a few seconds around the subtitle. Escalation may use:

- a more accurate Whisper model
- higher beam/best-of
- a language hint
- a prompt/glossary of validated character and place names
- nearby OCR
- 2–3 previous and following subtitle events
- stable speaker ID / diarization confidence / overlap flags
- previously validated speaker-to-character mappings
- title/episode IMDb candidates

For overlapping speech or uncertain speaker boundaries, the local review path may refine diarization or use diarization-aware crop/alignment rather than treating the region as a normal single-speaker segment.

The reviewer may improve spelling, grammar, punctuation and translation, but must not change meaning without strong evidence. Raw ASR is never overwritten.

## Fast OCR and proper names

Do not OCR every frame at full quality.

Preferred flow:

1. sample frames sparsely, e.g. every 0.5–1 s
2. run a cheap text detector
3. track/reuse stable text regions
4. recognize only new/changed regions
5. escalate relevant/uncertain regions to a stronger OCR model

High-value OCR includes names, location cards, messages, signs and plot-relevant documents. OCR evidence is especially valuable for correcting low-confidence proper names and for resolving a diarized speaker to a character when the scene provides explicit on-screen naming.

## Netflix-style French output

`src/netflix_style.py` and the `netflix` section of `config/style_rules.yaml` apply a French (France) timed-text profile before export.

Current checks/formatting include:

- 42 visible characters maximum per line
- 2 lines maximum
- syntactic/bottom-heavy line breaking when possible
- 5/6 second minimum duration and 7 second maximum
- 17 CPS preferred target and 20 CPS French SDH ceiling
- 2-frame minimum inter-subtitle gap
- chaining of short gaps below half a second when safe
- no silent truncation or paraphrasing to satisfy layout limits
- a machine-readable `output.netflix-report.json` for remaining violations

See `docs/NETFLIX_FR_STYLE.md` for the official Netflix references and the distinction between Netflix-style compliance and an official Netflix delivery package.

## SDH policy

This project includes:

- `docs/SDH_STYLE_GUIDE.md` for speaker IDs, diarization-aware rendering, sound effects, narration, and spoiler-safe naming
- `config/style_rules.yaml` for project-level SDH behavior

Highlights:

- use diarization to know when speakers change or overlap
- show speaker labels only when needed for clarity
- keep diarized speaker IDs separate from character identity
- prefer character names over actor names in visible subtitles
- do not reveal unrevealed names too early
- include only plot-pertinent or tonally relevant sound labels
- preserve raw ASR text and corrected text separately
- use French bracketed/lowercase generic SDH labels

## Music and sung lyrics

Music is routed separately from dialogue ASR.

Preferred selective flow:

```text
cheap music/singing detection
          |
          +--> instrumental -> concise SDH music label when relevant
          |
          +--> vocals/singing
                    |
               crop music window
                    |
            Demucs only if useful
                    |
              isolated vocals
                    |
              lyric transcription
                    |
        confidence + track/context review
```

Do not run Demucs over the entire episode by default. Run source separation only on musical windows where it is likely to improve lyric transcription or recover dialogue masked by music.

Intel's OpenVINO AI plugins for Audacity are documented as useful prior art for both Whisper-oriented transcription and Demucs-based source separation. The repo remains backend-agnostic so NVIDIA/CUDA and Intel/OpenVINO implementations can coexist.

See `docs/AUDIO_EVENTS_AND_MUSIC.md`.

## Confidence and proper-name review status

Already represented in the current code:

- low-confidence ASR words
- segment confidence review
- proper-noun candidate flags
- title-scoped IMDb character/actor candidates
- OCR hit data model and OCR-aware fusion scoring
- a `speaker_id` field at segment level

Still to be wired end-to-end:

- real Faster-Whisper ingestion instead of stub segments
- real diarization provider producing stable turns/overlaps/confidence
- explicit speaker-identity resolution separate from diarization
- real OCR frame extraction/detection
- scout ASR adapter
- evidence timeline + confidence router
- local audio crop + selective re-ASR
- persistent show/episode proper-name glossary
- persistent/validated speaker-to-character mappings
- translation confidence distinct from ASR confidence
- grammar, spelling and punctuation proofreading
- context-aware linguistic rewriting without semantic drift
- second-pass reviewer that can reject unsafe translation/correction suggestions
- shot-aware Netflix timing

## Audio and music policy

The project also includes:

- `docs/AUDIO_EVENTS_AND_MUSIC.md` for event detection, music windows, track recognition, source separation and lyrics policy
- `config/audio_analysis.yaml` for provider selection and thresholds
- `src/audio_music.py` for provider interfaces and stub data classes
- `src/track_recognition.py` for simple track-candidate scoring

Design direction:

- detect general sound events separately from dialogue ASR
- detect music and singing separately from general sound events
- recognize commercial tracks through pluggable providers when configured
- use lyrics overlap and fingerprint-like evidence as candidate-ranking signals
- keep track-identification metadata separate from visible subtitle output by default
- keep expensive music separation selective

## Performance and profiling

The goal is that roughly 90–95% of a normal episode remains on the cheap/normal path, while only difficult regions receive expensive processing. This is a target to measure, not an assumption.

Profile at least:

- real-time factor per stage
- percentage of segments escalated
- seconds of audio reprocessed
- diarization runtime
- number of speaker turns and overlaps
- low-confidence speaker boundaries
- speaker identity resolution/change count
- OCR frames and regions processed
- seconds sent to Demucs/source separation
- CPU/GPU time per provider
- quality gain from each escalation level

## Example CLI

```bash
subtitle-fusion run \
  --video /path/video.mkv \
  --title "Example Show" \
  --season 1 \
  --episode 3 \
  --imdb-title-id tt1234567 \
  --output-dir ./out
```

## Next steps

1. replace stub segments with real Faster-Whisper word/timestamp/confidence ingestion
2. add an evidence timeline and confidence router
3. wire first-class diarization turns, overlaps and stable speaker IDs
4. implement local audio crop + selective re-ASR
5. wire fast OCR detection and region-based recognition
6. add show/episode proper-name glossary persistence
7. add speaker-identity resolution separate from diarization
8. add Moonshine scout ASR adapter
9. add audio-event/music/singing routing
10. add selective Demucs + vocal ASR
11. add translation + grammar/spelling/context QA reviewer
12. add shot-change-aware Netflix timing
13. profile and calibrate thresholds on real episodes
