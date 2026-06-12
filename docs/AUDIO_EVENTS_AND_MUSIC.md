# Audio events and music recognition notes

This project treats the following as separate tasks:

1. detect that an audio event exists
2. classify the event
3. detect music
4. determine whether music is instrumental or sung
5. recognize a known commercial track when possible
6. transcribe sung lyrics only when confidence is high enough

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

These feed SDH labels such as:
- `[door slams]`
- `[footsteps approaching]`
- `[crowd cheering]`

### Music detection and characterization
Treat music separately from general sound events.
Recommended features:
- music present / absent
- vocal vs instrumental
- mood or energy when available
- optional instrument family hints

Typical visible outputs:
- `[tense music builds]`
- `[melancholic piano music]`
- `[upbeat song playing]`

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
- optionally crop a short excerpt
- query provider
- store title / artist / provider confidence in metadata
- do not expose title in visible subtitles unless the style policy requires it

### Sung lyrics
Lyrics transcription should not run on the mixed soundtrack by default.
Preferred flow:
1. detect likely sung music
2. isolate vocals with source separation
3. transcribe isolated vocals
4. keep only if confidence is sufficient
5. otherwise fall back to a short music label

Recommended source-separation hook names:
- `demucs`
- `spleeter`

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
    "source_separation": "demucs"
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

1. event detection provider hook
2. music detection provider hook
3. optional track-recognition provider hook
4. optional source-separation hook
5. lyric transcription only on high-confidence paths
