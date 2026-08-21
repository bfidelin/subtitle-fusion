# Song identification from lyrics

This document defines the intended song-identification path for `subtitle-fusion` when music is detected in a TV/movie soundtrack.

The goal is **not** to build or cache a lyrics database. The goal is to use a small number of distinctive sung-word hypotheses to identify the track, then keep only the minimum metadata/evidence required for subtitle decisions.

## Why a lyrics-search path exists

Audio fingerprinting is excellent when a clean enough excerpt is available, but TV/movie mixes are often difficult:
- dialogue overlaps the music
- the song is quiet in the background
- only a short fragment is audible
- the soundtrack uses a remix/live/edit/version
- effects or score mask part of the recording

In those cases, a few correctly transcribed sung words can be more useful than the raw fingerprint.

## Recommended identification flow

```text
music window
   |
   +-> singing/vocal scout
   |
   +-> crop only the relevant window
   |
   +-> optional Demucs/HTDemucs vocal isolation
   |
   +-> ASR on vocals
   |      -> word confidences
   |      -> n-best/alternate fragments where inexpensive
   |
   +-> select distinctive lyric fragments
   |      -> preferably 5-15 useful tokens
   |      -> avoid generic phrases when possible
   |      -> preserve language and punctuation variants
   |
   +-> web search for exact/fuzzy fragments
   |      -> candidate title + artist + version
   |
   +-> in parallel when useful:
   |      Chromaprint -> AcoustID lookup
   |
   +-> candidate fusion
   |      -> lyric evidence
   |      -> fingerprint evidence
   |      -> title/artist/version consistency
   |
   +-> MusicBrainz metadata confirmation
   |
   `-> final track candidate + confidence
```

## Lyric fragment selection

Search queries should be built from the most discriminative words available, not from the entire ASR output.

Prefer fragments that:
- contain uncommon word combinations
- have several medium/high-confidence words
- are contiguous enough to resemble the original lyric
- exclude repeated filler such as `oh`, `yeah`, `la la`, etc. unless no better evidence exists
- retain likely proper nouns when confidence is reasonable

Generate a small query set rather than dozens of variants:
1. exact quoted fragment
2. punctuation-normalized fragment
3. one or two fuzzy alternatives for low-confidence words
4. optional title/artist hints if another provider already returned a candidate

The search engine is a **candidate generator**, not the authority.

## Candidate scoring

Keep independent evidence dimensions instead of one opaque score:

```text
lyrics_query_confidence
lyrics_result_match
fingerprint_confidence
metadata_consistency
version_consistency
final_track_confidence
```

A practical fusion rule should reward agreement between independent signals. Examples:

```text
strong lyric match + strong AcoustID match
-> very high confidence

strong lyric match + no usable fingerprint
-> accept only if title/artist evidence is consistent across results

weak lyric match + strong fingerprint
-> prefer fingerprint candidate, keep lyric result as secondary evidence

lyrics and fingerprint disagree
-> do not silently choose; mark for wider search/review
```

## MusicBrainz role

MusicBrainz is primarily a **metadata confirmation layer**, not the first lyrics search engine.

Use it after a likely song/recording has been found to normalize:
- title
- artist
- recording identity / MBID
- release/version relationships when useful

MusicBrainz Web Service facts relevant to implementation:
- non-commercial API usage is free
- no API key is currently required for normal reads
- a meaningful `User-Agent` is required
- clients should not exceed one request per second

Reference: https://musicbrainz.org/doc/MusicBrainz_API

## AcoustID / Chromaprint role

AcoustID remains a valuable independent signal:
- generate an audio fingerprint with Chromaprint
- query AcoustID for matching recordings
- use returned MusicBrainz recording IDs when available

AcoustID's public service requires an application client key and documents a maximum of three requests per second for the free non-commercial service.

Reference: https://acoustid.org/webservice

Fingerprinting and lyric search should be considered complementary, not mutually exclusive.

## Copyright/data-handling policy

Do **not** scrape or persist full copyrighted lyrics as a project dataset.

For identification, retain only what is necessary for reproducibility/debugging, for example:
- the short ASR fragment used as a search query
- normalized query variants
- candidate song title/artist/version
- result/source identifiers or URLs when useful
- match/confidence scores

If a provider returns a full lyrics page, do not copy the full lyrics into `output.debug.json` or repository fixtures. Test fixtures should use synthetic/public-domain text.

## Interaction with lyric subtitles

Track identification and lyric transcription are related but separate decisions.

```text
track identified
   |
   +-> metadata/context can improve local vocal ASR
   |
   +-> known title/artist can help detect wrong ASR language/version
   |
   `-> does NOT authorize copying web lyrics into subtitles
```

Visible sung subtitles should still come from the media evidence and the project's translation/review path. External lyric matches can be used as contextual evidence to resolve uncertainty, but automatic wholesale replacement with web lyrics is forbidden.

## Suggested debug shape

```json
{
  "music": {
    "track_candidate": {
      "title": "Example Song",
      "artist": "Example Artist",
      "version": null,
      "final_confidence": 0.94,
      "musicbrainz_recording_id": "..."
    },
    "identification": {
      "lyrics_queries": [
        {
          "fragment": "distinctive five to fifteen word fragment",
          "asr_confidence": 0.78,
          "result_match": 0.91
        }
      ],
      "fingerprint": {
        "provider": "acoustid",
        "score": 0.97
      },
      "decision": "lyrics_and_fingerprint_agree"
    }
  }
}
```

## Performance policy

Network lookups are only allowed for candidate music windows. Do not search the web for every audio segment.

Cache successful track-identification results by a stable key such as:
- media fingerprint + time window
- audio fingerprint when available
- normalized high-confidence lyric fragment

Respect provider rate limits and back off on errors. A network failure must never block normal subtitle generation; the pipeline should fall back to local evidence and a generic music/lyrics caption when necessary.

## Implementation order

1. singing/music candidate windows
2. selective Demucs/HTDemucs vocal isolation when useful
3. vocal ASR with word confidence
4. distinctive-fragment selector
5. pluggable web lyric-search candidate provider
6. optional Chromaprint/AcoustID provider in parallel
7. candidate-fusion scorer
8. MusicBrainz metadata confirmer/cache
9. debug evidence + benchmark counters
10. tests with synthetic lyric fragments and fake provider responses
