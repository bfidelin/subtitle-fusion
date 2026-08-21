# Audio events and music recognition notes

This project treats the following as separate tasks:

1. detect that an audio event exists
2. classify the event
3. detect music
4. determine whether music is instrumental or sung
5. recognize a known commercial track when possible
6. transcribe sung lyrics only when confidence is high enough

The global performance policy is described in `docs/FAST_SCOUT_PIPELINE.md`: use very cheap whole-episode scouts, then run expensive processing only on interesting windows.

Song identification from sung-word fragments is specified in [`docs/SONG_IDENTIFICATION.md`](SONG_IDENTIFICATION.md).

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
Instead, the project should support pluggable music recognition providers and **two complementary identification paths**:

```text
                  selected music window
                         |
              +----------+----------+
              |                     |
       lyric-based path        fingerprint path
              |                     |
      Demucs if useful         Chromaprint
      vocal ASR                -> AcoustID
      distinctive fragments          |
      -> web candidate search         |
              +----------+----------+
                         |
                   candidate fusion
                         |
                 MusicBrainz confirm
```

The lyric-based path is especially valuable when soundtrack dialogue/effects, short excerpts, low music level, remixes or edits make fingerprint matching unreliable.

The fingerprint path remains valuable because it is an independent signal. Agreement between lyric evidence and AcoustID evidence should sharply increase final confidence.

MusicBrainz is primarily a metadata confirmation/normalization layer after a likely recording has been found. For non-commercial use its API is free, requires a meaningful `User-Agent`, currently needs no read API key, and documents a maximum of one request per second.

AcoustID's public non-commercial service requires an application client key and documents a maximum of three requests per second.

References:
- https://musicbrainz.org/doc/MusicBrainz_API
- https://acoustid.org/webservice
- [`docs/SONG_IDENTIFICATION.md`](SONG_IDENTIFICATION.md)

Do not treat a web search result or a single provider response as authoritative. Store candidate title / artist / version / provider confidence and cross-check independent evidence where possible.

### Sung lyrics
Lyrics transcription should not run on the mixed soundtrack or over the entire episode by default.

Preferred selective flow:
1. detect a likely music window cheaply
2. classify whether singing/vocals are likely
3. crop only that musical window
4. when useful, isolate vocals with source separation
5. transcribe isolated vocals
6. select a few distinctive high-value lyric fragments
7. search the web for candidate song/title/artist matches
8. optionally run Chromaprint/AcoustID in parallel
9. fuse lyric/fingerprint/metadata evidence
10. use track context to re-evaluate uncertain vocal ASR
11. keep visible lyrics only when confidence and relevance are sufficient
12. otherwise fall back to a concise music label

Recommended source-separation hook names:
- `demucs`
- `openvino_demucs`
- `spleeter` as an optional alternative

Do **not** run Demucs over an entire 45-minute episode by default. The confidence/event router should normally send only musical or heavily masked windows to source separation.

External lyric search is for **identification/context**, not for wholesale lyric replacement. Do not scrape or persist full copyrighted lyrics as project data. Keep only short query fragments, candidate metadata, source identifiers/URLs and confidence evidence needed for debugging/reproducibility.

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
                    distinctive lyric fragments
                         /                \
                   web search         AcoustID
                         \                /
                          candidate fusion
                               |
                         MusicBrainz confirm
                               |
                     lyric confidence/review
```

A music or singing flag can also explain poor speech ASR and trigger a local dialogue re-evaluation.

## Pipeline policy

### Visible subtitle policy
Visible subtitle output should prefer:
- concise SDH sound labels
- concise music labels
- sung lyrics only when intelligible and important

A successfully identified track does **not** automatically mean title/artist should be shown in every visible subtitle. Identification primarily improves context, confidence and metadata unless the active style policy calls for a track label.

### Metadata policy
Store recognition details in metadata/debug JSON:
- provider name(s)
- track title candidate
- artist candidate
- recording/version candidate
- MusicBrainz recording ID when confirmed
- provider/fingerprint confidence
- lyric-query fragment(s) and ASR confidence
- lyric search match score
- excerpt timestamps
- lyrics confidence
- source separation method
- music/singing classifier confidence
- whether the window was escalated and why
- final track confidence and fusion reason

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
      "title": "Example Song",
      "artist": "Example Artist",
      "version": null,
      "musicbrainz_recording_id": "...",
      "confidence": 0.94
    },
    "identification": {
      "lyrics_query_confidence": 0.78,
      "lyrics_result_match": 0.91,
      "fingerprint_provider": "acoustid",
      "fingerprint_confidence": 0.97,
      "decision": "lyrics_and_fingerprint_agree"
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

### Track identification confidence
Prefer:
- independent agreement between lyric search and fingerprinting
- consistent title/artist/version metadata
- explicit unknown/review when sources disagree

Never silently force a track identity because a web search returned a plausible-looking result.

### Do not over-label
Avoid turning every audible element into a caption.

## Integration priority for this repo

1. cheap AudioSet/YAMNet-like event/music/singing scout
2. event timeline merged with ASR/OCR evidence
3. selective source-separation hook
4. vocal ASR on routed windows
5. distinctive lyric-fragment selector
6. pluggable web lyric-search candidate provider
7. optional Chromaprint/AcoustID provider in parallel
8. candidate fusion + MusicBrainz metadata confirmation/cache
9. lyrics confidence + contextual review
10. profiling: music windows, web lookups, fingerprint matches, seconds sent to Demucs, cache hits and quality gain
