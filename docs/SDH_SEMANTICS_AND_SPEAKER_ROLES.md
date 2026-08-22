# SDH semantics, speaker roles and sparse visual identity

Last verified: **2026-08-22**.

This document records how `subtitle-fusion` should represent SDH semantics before rendering locale/profile-specific punctuation and labels. It also defines the multimodal speaker-role and visual-identity model discussed during review of a real SDH SRT.

The core rule is:

> **Preserve semantic intent first; render punctuation, labels and typography second.**

A source SRT may encode meaning with punctuation or layout conventions that differ by locale. The internal model must not confuse those conventions with the underlying event.

## 1. Evidence dimensions must stay separate

Do not collapse these fields into one opaque identity:

```text
speaker_id          = SPEAKER_05      # acoustic diarization cluster
speaker_identity    = Judy            # character/person hypothesis
speaker_role        = narrator        # dialogue / narrator / announcer / etc.
speaker_visible     = false           # visual evidence
active_face_track   = null            # face actually speaking, if known
voice_confidence    = 0.96
face_confidence     = null
role_confidence     = 0.98
visibility_confidence = 0.91
```

Important distinctions:
- diarization is not identity
- identity is not visibility
- no detected face is not proof of off-screen speech
- off-screen is not automatically voice-over
- voice-over is not automatically narrator
- narrator is a semantic/editorial role, not merely a voice that is never visible
- the same human can have different roles in different scenes
- spoiler-safe display identity may differ from backend identity knowledge

## 2. Speaker-role taxonomy

Recommended initial role vocabulary:

```text
dialogue
off_screen
voice_over
narrator
announcer
phone
recorded_voice
electronic_media
unknown
```

These roles may coexist with separate transport/source metadata, for example `source=telephone`, `source=television`, or `source=loudspeaker`.

### Narrator
A narrator is inferred from several kinds of evidence:
- a trusted source subtitle explicitly says `[narrator]` / `[narrateur]`
- a recurrent voiceprint matches a previously enrolled narrator role
- the text is semantically narrative, explanatory or presentational rather than conversational
- the turn occurs in an intro, recap, transition, montage, outro or explanatory bridge
- the speaker is consistently not represented as an in-scene conversational participant
- visual evidence does not contradict the role

No single weak signal should force the role.

### Voice-over
A voice-over can be a character or other speaker heard while not physically present in the current scene. It is not automatically narration.

Examples:
- internal monologue
- flashback narration by a character
- letter/message being read over another scene
- documentary interview audio over B-roll

### Off-screen
`off_screen` means the speaker belongs to the scene but is not currently visible/camera-confirmed. It must remain distinct from `voice_over` and `narrator`.

### Announcer
Use for program announcements, promos, public-address announcements, competition introductions or closing calls-to-action when this is semantically more accurate than `narrator`.

A recurrent program voice may switch between `narrator` and `announcer` depending on context.

## 3. Contextual LLM role classification

A compact contextual reviewer is a strong source of role evidence because narrative language is often obvious from discourse structure even when audio/vision alone are ambiguous.

Suggested input package:

```text
previous 2-3 cues
current raw text
next 2-3 cues
speaker_id
voiceprint role matches
speaker_visible / active face evidence
segment position in episode
shot/scene type if known
trusted source labels
OCR/title-card evidence
```

Suggested output schema:

```json
{
  "role": "narrator",
  "confidence": 0.98,
  "reason": "third-person case introduction during program intro"
}
```

The LLM result is evidence, not final truth. Contradictions from trusted source labels, strong active-speaker evidence or scene context must remain inspectable.

## 4. Role fusion policy

Prefer explicit independent evidence over one opaque score.

Example narrator evidence:

```text
trusted source label [narrator]        very strong
known narrator voiceprint              strong
LLM semantic role=narrator             strong
intro/recap/transition/outro context   supporting
never matched to an in-scene face      supporting only
active visible face contradiction      strong negative
normal turn-taking conversation        negative
```

Do not hard-code the illustrative weights below as universal constants, but a calibrated implementation may use a structure such as:

```text
trusted source role label       +0.60
known role voiceprint           +0.30
LLM semantic role               +0.25
structural intro/outro context  +0.10
consistent no-face history      +0.10
strong contradictory face role  -0.50
```

Always retain component scores/reasons in debug output.

## 5. Role memory across a series

Trusted subtitle labels can supervise recurring role enrollment.

Example:

```text
[narrator] in a trusted SDH source
        +
pyannote speaker embedding
        -> enroll role voiceprint: narrator
```

On later episodes:

```text
speaker embedding
  -> narrator voice centroid match
  -> context review
  -> narrator hypothesis
```

This allows narrator detection to become almost free after one or more well-labelled episodes.

Keep role enrollment bounded and conservative just like character voiceprints. Do not permanently learn from one weak/ambiguous cue.

## 6. Sparse visual identity: do not scan every frame

Visual analysis should be event-driven.

Primary triggers:
- new shot
- start of a speaker turn
- end of a speaker turn
- shot change during a speaker turn
- speaker change / overlap
- long turn requiring a midpoint refresh
- face-track loss
- new face entering the frame

Recommended sampling around a normal turn:

```text
speaker turn start
   -> frame roughly +200 to +300 ms inside speech

speaker turn end
   -> frame roughly -200 to -300 ms inside speech
```

Do not sample exactly at the acoustic boundary when a nearby interior frame is likely to be sharper and more representative.

For a long turn (initial heuristic: >6-8 s), optionally add one midpoint frame.

## 7. Shot-aware visual policy

A shot map is shared infrastructure, not a face-only stage.

```text
SHOT MAP
  -> timing
  -> OCR sampling
  -> subtitle placement stability
  -> face-track refresh
  -> active-speaker sampling
  -> structural intro/recap/outro evidence
```

At a shot boundary:
- invalidate/revalidate visual continuity as needed
- choose a representative frame shortly after the cut rather than the transition frame itself
- optionally evaluate two nearby frames and keep the sharper/cleaner face crop

A long shot may still require refresh because a person can enter or leave without a cut.

## 8. Face detection, tracking and identity

Keep the visual stages separate:

```text
frame
  -> face detection
  -> face_track_id
  -> selected good face crops
  -> face embedding
  -> face cluster/centroid
  -> character identity hypothesis
```

Suggested provider interface:

```text
VisualIdentityProvider
  -> FaceDetector
  -> FaceTracker
  -> FaceEmbeddingProvider
  -> IdentityMatcher
```

Provider choice must remain swappable. InsightFace/SCRFD/ArcFace and facenet-style backends are candidate implementations, but model licensing must be reviewed separately from library code licensing before distribution/commercial use.

Do not compute a fresh identity resolution for every frame. Once a stable face track/cluster has a strong identity, reuse it until evidence changes.

## 9. Active speaker fusion

Active-speaker detection answers a different question from face identity:

```text
FACE_07 = Judy              # who is this face?
FACE_07 active = true       # is this face speaking now?
SPEAKER_02 = Judy           # which acoustic speaker is this?
```

Target active-speaker policy:
- run only on speech windows
- reuse existing face tracks
- benchmark LR-ASD first
- keep TalkNet/other implementations pluggable
- reset/refresh around shot changes

Strong multimodal agreement:

```text
voiceprint: SPEAKER_02 -> Judy
face identity: FACE_07 -> Judy
active speaker: FACE_07 speaking
      -> very high confidence association
```

## 10. SDH semantic events discovered in real subtitle review

A real U.S. English SDH SRT reviewed for this project exposed several semantics that must be represented explicitly rather than treated as arbitrary punctuation.

### Dual speakers
Source form may use one leading hyphen per line:

```text
-First speaker.
-Second speaker.
```

Internal representation should store two speaker events. The renderer chooses locale/profile syntax. Netflix fr-FR uses a hyphen followed by a space; U.S. English uses a hyphen without the space in its current guide.

### Speaker ID layout variants
A source can contain both:

```text
[narrator]
Dialogue text
```

and:

```text
[narrator] Dialogue text
```

Ingestion must normalize both to the same semantic structure. Do not rely on the bracket label and dialogue sharing one physical SRT line.

### Abrupt interruption vs hesitation/trail-off
U.S. English SDH may use `--` for abrupt interruption by another speaker/action/sound. French Netflix-style output uses an ellipsis for interruption according to the fr-FR profile.

Therefore store semantic punctuation intent:

```text
continuation_kind = abrupt_interruption
```

rather than preserving `--` blindly across translation/localization.

Use a separate semantic value for:

```text
continuation_kind = hesitation
continuation_kind = trail_off
continuation_kind = long_pause
continuation_kind = mid_sentence_pickup
```

The renderer then applies locale-specific punctuation.

### Smart ellipsis normalization
Use U+2026 `…` when the active style guide calls for an ellipsis. A source file may contain legacy `...`; preserve raw evidence but normalize rendered punctuation according to the profile.

### Paralinguistic speech
Do not discard automatically:

```text
Mm-hmm
Mm
Uh
Um
```

These are spoken/paralinguistic tokens, not generic sound effects. Keep them when relevant to plot, mood, characterization or conversational meaning; allow explicit editorial reduction only when readability requires it.

### Sound effects interrupting dialogue
A cue may contain a semantic pause plus a sound label such as:

```text
There's a difference in saying…
[scoffs] "I'm not answering you,"
```

Represent the sound event separately from dialogue text so timing/rendering can decide whether to keep it inline, split it, or synchronize it independently.

### Reported/quoted speech
Dialogue can quote another person's earlier words across cue boundaries. Preserve quote state across segmentation so rewrapping or translation does not create unbalanced quotation marks or accidentally turn reported speech into a new speaker event.

### Unknown/not-yet-revealed speakers
Use generic, spoiler-safe labels until the narrative establishes identity. Backend identity knowledge must never force premature visible naming.

### Electronic/remote voices
Phone, television, loudspeaker, GPS, recording and other electronic-media speech should carry explicit source metadata. This can affect italics and role rendering, but must not be inferred solely from lack of a face.

### Foreign-language speech
When language is known and relevant, store the actual detected language and whether it is intended to be understood. Do not collapse all cases into a generic `foreign_language` label.

### Silence
Plot-pertinent silence or abrupt cessation of important music can be an SDH event. Silence is therefore a possible semantic event, not merely absence of detections.

## 11. Music, theme songs and credits

Keep separate concepts:

```text
music_present
singing_present
track_identity
music_role = underscore | source_music | opening_theme | ending_theme | unknown
lyrics_plot_relevant
credits_sequence
```

Ending/opening theme recognition can combine:
- position near episode boundaries
- recurring audio fingerprint across episodes
- OCR density/pattern characteristic of credits
- low dialogue density
- persistent music window
- optional track identification

Once a series theme is confidently learned, store a local fingerprint/centroid and recognize it without repeated internet lookup or source separation.

Netflix fr-FR guidance says opening/ending theme songs should normally be subtitled only when clearly plot-pertinent or specifically instructed; SDH has broader same-language song requirements. The renderer/profile must decide visible treatment independently from recognition metadata.

## 12. Suggested semantic data model

```json
{
  "speaker": {
    "id": "SPEAKER_05",
    "identity": null,
    "identity_confidence": null,
    "role": "narrator",
    "role_confidence": 0.98,
    "visible": false,
    "visibility_confidence": 0.91,
    "active_face_track": null
  },
  "speech_semantics": {
    "continuation_kind": "abrupt_interruption",
    "quoted_speech": false,
    "paralinguistic": false
  },
  "source": {
    "kind": "voice_over",
    "electronic_medium": null
  }
}
```

For a sound event:

```json
{
  "event_type": "sound_effect",
  "label": "scoffs",
  "start": 739.4,
  "end": 739.9,
  "confidence": 0.88,
  "plot_relevant": true
}
```

## 13. Rendering policy

The renderer, not the ASR, decides profile-specific notation.

Examples of semantic-to-render mapping:

```text
two_speakers            -> hyphen style per locale
abrupt_interruption     -> `--` en-US / `…` fr-FR profile
hesitation              -> `…` when warranted
speaker_role narrator   -> [narrator] / [narrateur] only when needed
sound effect            -> [scoffs] / localized sound label
song lyric              -> ♪ ... ♪ + italics when profile calls for it
voice-over              -> italics when profile calls for it
```

Formatting tags/prefixes must not contaminate CPL/CPS/WPM text metrics.

## 14. QC rules to add

Recommended deterministic checks:
- source `...` normalized to U+2026 when rendered as ellipsis
- locale-inappropriate interruption marker
- unbalanced quotation marks across segmentation
- dual-speaker cue with more than one speaker on a line
- speaker ID detached from its dialogue after rendering when avoidable
- repeated/unnecessary speaker ID
- narrator label contradicted by strong visible/scene evidence
- `no_face -> narrator` inference attempted without supporting evidence
- voice-over/off-screen conflation
- role changes without evidence/reason
- electronic-media voice rendered without required profile treatment
- paralinguistic token removed without an explicit editorial reason
- relevant sound event swallowed by dialogue segmentation

## 15. Implementation order

1. add semantic fields for role / visibility / continuation / source
2. parse SDH speaker/sound labels from reusable subtitle sources into evidence, not raw dialogue text
3. add locale-aware punctuation renderer for interruption/ellipsis/dual-speaker syntax
4. add contextual speaker-role reviewer with structured output
5. connect trusted `[narrator]` labels to conservative role-voiceprint enrollment
6. add shared shot map
7. add sparse face detector/tracker/embedding provider
8. sample visual evidence at shot boundaries and speaker-turn start/end, with midpoint/event refresh only when useful
9. add sparse LR-ASD and multimodal face/voice/context fusion
10. add series-level recurring role/theme memory and benchmark all visual/audio enrichment stages

## 16. Current implementation status

Implemented today:
- WhisperX/pyannote speaker turns and embeddings
- conservative per-series voiceprint store
- raw/debug evidence model

Planned/not yet end-to-end:
- speaker-role resolver
- contextual LLM role classifier
- narrator-role enrollment
- shot map
- face detector/tracker/identity provider
- LR-ASD active speaker
- opening/ending-theme recurring fingerprint memory
- locale-aware semantic interruption renderer

Do not describe the planned items above as runtime-complete.

## References

Netflix:
- https://partnerhelp.netflixstudios.com/hc/en-us/articles/217351577-French-France-Timed-Text-Style-Guide
- https://partnerhelp.netflixstudios.com/hc/en-us/articles/217350977-English-USA-Timed-Text-Style-Guide

Project:
- `docs/STANDARDS_AND_PRACTICES.md`
- `docs/FAST_SCOUT_PIPELINE.md`
- `docs/AUDIO_EVENTS_AND_MUSIC.md`
- `docs/SONG_IDENTIFICATION.md`
