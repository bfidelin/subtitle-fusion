# Audio events and music recognition notes

This project treats the following as separate tasks:

1. detect that an audio event exists
2. classify the event
3. detect music
4. determine whether music is instrumental or sung
5. recognize a known commercial track when possible
6. transcribe sung lyrics only when confidence is high enough

The global performance policy is described in `docs/FAST_SCOUT_PIPELINE.md`: use very cheap whole-episode scouts, then run expensive processing only on interesting windows.

## Recommended architecture

### General sound events
Use a broad audio event classifier first.
Suggested families:
- AudioSet / YAMNet-like classifiers for general sound events
- optional custom event heads for project-specific labels

Typical outputs:
- `door_slam`
- `footsteps`
- `gunshot`
- `glass_break`
- `crowd_cheer`
- `thunder`
- `music`
- `singing`

These feed SDH labels such as:
- `[porte qui claque]`
- `[pas qui approchent]`
- `[la foule applaudit]`

The first classifier is primarily a router: it should find candidate windows cheaply rather than produce final prose directly.

### Music detection and characterization
Treat music separately from general sound events.
Recommended features:
- music present / absent
- vocal vs instrumental
- likely singing window
- mood or energy when available
- optional instrument family hints

Typical visible outputs:
- `[musique tendue]`
- `[musique mélancolique au piano]`
- `[chanson entraînante]`

### Known-track recognition
There is no generic "public Shazam REST" integration assumed by this project.
Instead, the project should support pluggable music recognition providers.

Recommended provider order:
1. `shazamkit` for app/platform integrations where available
2. `audd` for a simple hosted recognition API
3. `acrcloud` for larger-scale recognition workflows
4. `none` if no external music recognition provider is configured

Track recognition should be metadata-first:
- detect a likely music window
- crop a short excerpt
- query provider only for that excerpt
- store title / artist / provider confidence in metadata
- do not expose title in visible subtitles unless the style policy requires it

### Sung lyrics
Lyrics transcription should not run on the mixed soundtrack or over the entire episode by default.

Preferred selective flow:
1. detect a likely music window cheaply
2. classify whether singing/vocals are likely
3. crop only that musical window
4. when useful, isolate vocals with source separation
5. transcribe isolated vocals
6. compare ASR confidence with track/context evidence
7. keep lyrics only when confidence and relevance are sufficient
8. otherwise fall back to a concise music label

Recommended source-separation hook names:
- `demucs`
- `openvino_demucs`
- `spleeter` as an optional alternative

Do **not** run Demucs over an entire 45-minute episode by default. The confidence/event router should normally send only musical or heavily masked windows to source separation.

### Intel/OpenVINO prior art

The Intel OpenVINO AI plugins for Audacity are useful prior art because they demonstrate:
- Whisper-oriented transcription through an OpenVINO/whisper.cpp path
- Demucs-based music separation into vocals/instrumental or multiple stems

Reference:
- https://github.com/intel/openvino-plugins-ai-audacity

`subtitle-fusion` should reuse the architectural idea while keeping provider interfaces backend-agnostic. On NVIDIA systems the heavy path may use CUDA, while OpenVINO remains useful on Intel hardware.

## Interaction with the fast scout pipeline

Audio processing participates in the same escalation policy as ASR/OCR:

```text
whole episode
    |
    v
cheap audio-event scout
    |
    +--> ordinary speech/silence -> no extra music work
    |
    +--> music, no vocals -> metadata / concise SDH label
    |
    +--> likely singing -> selective crop
                              |
                              v
                         Demucs if useful
                              |
                              v
                         vocal ASR
                              |
                              v
                     lyric confidence/review
```

A music or singing flag can also explain poor speech ASR and trigger a local dialogue re-evaluation.

## Pipeline policy

### Visible subtitle policy
Visible subtitle output should prefer:
- concise SDH sound labels
- concise music labels
- sung lyrics only when intelligible and important

### Metadata policy
Store recognition details in metadata/debug JSON:
- provider name
- track title candidate
- artist candidate
- provider confidence
- excerpt timestamps
- lyrics confidence
- source separation method
- music/singing classifier confidence
- whether the window was escalated and why

## Suggested JSON shape

```json
{
  "events": [
    {"label": "door_slam", "score": 0.88}
  ],
  "music": {
    "present": true,
    "vocal": true,
    "mood": "tense",
    "track": {
      "provider": "audd",
      "title": "Example Song",
      "artist": "Example Artist",
      "confidence": 0.82
    },
    "lyrics_detected": true,
    "lyrics_confidence": 0.71,
    "source_separation": "demucs",
    "escalation_reason": "singing_detected"
  }
}
```

## Decision rules

### Show a sound label when
- it matters for plot
- it changes scene understanding
- it adds tone or suspense that is not fully visible

### Show music information when
- mood matters for interpretation
- a song enters or leaves meaningfully
- lyrics are plot-relevant and intelligible

### Do not over-label
Avoid turning every audible element into a caption.

## Integration priority for this repo

1. cheap AudioSet/YAMNet-like event/music/singing scout
2. event timeline merged with ASR/OCR evidence
3. optional track-recognition provider hook
4. selective source-separation hook
5. lyric transcription on isolated vocals only when routed there
6. lyrics confidence + contextual review
7. profiling: number of music windows, seconds sent to Demucs, and quality gain
