# Professional subtitle standards and practices

Last verified: **2026-08-21**.

This document is the normative decision record for subtitle-fusion. It distinguishes hard format/interoperability standards from broadcaster/platform style guides. Platform rules are profiles, not universal laws.

## 1. Output strategy

Keep one rich internal evidence model and derive simple delivery files from it.

Active output hierarchy:

1. `output.debug.json` — canonical evidence/debug artifact; never discard raw ASR/OCR/diarization evidence.
2. **SRT** — primary playback output for Jellyfin/Android TV compatibility.
3. ASS — optional rich local output; not required by the main playback path.
4. WebVTT — only if a web delivery use case is added later.

### IMSC / TTML status

W3C IMSC Text Profile 1.3 remains useful standards background, but it is **inactive in subtitle-fusion**:
- no exporter
- no runtime dependency
- no generated IMSC/TTML artifact
- no active implementation milestone
- no CI/profile-validation requirement

Do not add IMSC/TTML work unless it is explicitly re-enabled in a future decision.

Historical/reference material:
- https://www.w3.org/news/2026/imsc-text-profile-1-3-is-now-a-w3c-recommendation/
- https://www.w3.org/TR/ttml-imsc1.3/
- https://tech.ebu.ch/publications/tech3380

### SRT placement policy

SRT remains the primary output even when collision avoidance is needed. Some Jellyfin/Android TV playback paths support ASS-style alignment tags embedded in SRT, such as:

```srt
{\an8}Subtitle moved to the top.
```

Treat these as **compatibility extensions**, not portable SRT standard features. The renderer must preserve a safe fallback when a player ignores them.

Planned placement logic:
- bottom-center by default
- move to top-center when plot-relevant on-screen text occupies the lower subtitle region
- use OCR/text bounding boxes as avoidance evidence
- later include face/important-region boxes where useful
- keep placement stable across a shot/sequence to avoid top/bottom ping-pong
- prefer changing placement at shot boundaries when possible
- retain placement reason/confidence in debug evidence

Suggested debug fields:
- `placement_region`
- `placement_confidence`
- `placement_reason`
- `avoid_boxes`
- `sticky_until`

Placement tags are **planned, not implemented yet**.

References for the compatibility behavior:
- https://jellyfin.org/posts/androidtv-v0.18.0/
- https://subtitleedit.github.io/subtitleedit/reference/subrip.html

## 2. Netflix French profile

The existing `src/netflix_style.py` remains the primary fr-FR style/QC profile. It is a Netflix-style profile for our generated output; it is not a claim that files are official Netflix delivery packages.

Official references:
- General requirements: https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements
- Timing: https://partnerhelp.netflixstudios.com/hc/en-us/articles/360051554394-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines
- French (France): https://partnerhelp.netflixstudios.com/hc/en-us/articles/217351577-French-France-Timed-Text-Style-Guide
- Templates: https://partnerhelp.netflixstudios.com/hc/en-us/articles/219375728-Timed-Text-Style-Guide-Subtitle-Templates

### Layout

- maximum 42 visible characters per line for French
- maximum 2 lines
- prefer syntactic/clause-level line breaks
- prefer a bottom-heavy two-line shape when both breaks are linguistically good
- avoid one/two-word orphan top lines
- do not split tightly bound units such as article+noun, adjective+noun, subject+verb when avoidable
- never silently truncate/paraphrase merely to satisfy layout
- avoid covering plot-relevant on-screen text when a supported placement alternative is available

### Timing

- cue in-time should normally be on the first audio frame or within 1–2 frames
- minimum duration: 20 frames (roughly 5/6 s at 24 fps)
- maximum duration: 7 s
- minimum inter-cue gap: 2 frames at every frame rate
- gaps shorter than 0.5 s should normally be chained/closed to the 2-frame gap where safe
- where no next cue follows, allow useful reading tail after speech, while respecting shot-change rules
- dialogue that genuinely crosses a cut may have a cue crossing the cut; otherwise avoid hanging a cue over a shot/scene change
- never expose a punchline/plot point before the corresponding visible reaction

### Shot-change rules

Shot boundaries are first-class timing evidence, not a cosmetic afterthought.

Compute a shot map once and reuse it for:
- subtitle in/out snapping
- OCR sampling
- active-speaker sampling
- scene/recap boundary detection
- placement stability/reset decisions

Within the Netflix half-second shot-change window, cue boundaries may be moved to the cut to produce stable timing. Preserve the 2-frame gap.

### Reading speed

For French SDH, use 17 CPS as the normal target and 20 CPS as a warning/hard-profile ceiling where appropriate. Also report WPM as a second metric; CPS alone can hide dense short-word dialogue.

Mechanical formatting must not rewrite meaning to reduce CPS. Text reduction/condensing is an explicit editorial operation with traceable before/after text.

### French language/editorial details

- preserve approved proper names and diacritics
- do not translate proper names unless an approved localized form exists
- do not neutralize slang/register/dialect
- numbers, abbreviations, units and punctuation should follow fr-FR rules
- for SDH based on a French dub, match the dubbed audio/script as closely as timings/reading speed permit

## 3. SDH / accessibility semantics

Captions are not only dialogue.

Visible SDH output should include only information needed to understand the program:
- meaningful non-speech sounds
- speaker identification when the speaker is not otherwise clear
- music/lyrics when narratively relevant
- plot-pertinent on-screen text

Rules:
- identity and visibility are different evidence
- `SPEAKER_03` is never a character name by itself
- a failed face detector does not prove off-screen speech
- prefer character names to actor names in visible cues
- never reveal a character name before the story has established it
- once a speaker is established, avoid needless repeated name labels
- generic sound/speaker labels should remain concise
- identify a foreign language when known/relevant rather than emitting a vague `[foreign language]`

W3C media-accessibility requirements similarly treat captions as synchronized dialogue plus important non-speech information and require speaker distinction when needed.

References:
- https://www.w3.org/WAI/media/av/captions/
- https://www.w3.org/WAI/media/av/

## 4. On-screen text / forced narrative

OCR evidence must not automatically become a subtitle.

Include on-screen text only when plot-pertinent. If dialogue and on-screen text overlap, choose the more important message rather than crushing both into unreadable cues.

- suppress redundant OCR/FN when dialogue already conveys the same text
- time the FN approximately to the visible text duration when reading speed/dialogue allows
- short on-screen-text FNs may use ALL CAPS in the Netflix fr-FR profile
- long letters/messages/prologues should favor readable sentence case/italics
- preserve the raw OCR string and confidence in debug data
- use the OCR bounding box as layout-avoidance evidence even when the OCR text itself is not emitted as a subtitle

This creates two separate uses for video text detection:
1. semantic evidence: what does the on-screen text say?
2. layout evidence: where should dialogue subtitles not be placed?

## 5. Translation best practices

Translation is a semantic stage after source transcription/timing evidence, not a formatter side effect.

Recommended pipeline:

```text
source transcript
  -> terminology / proper-name glossary
  -> translation candidate
  -> semantic consistency check
  -> reading-speed / line-break adaptation
  -> bilingual or model QA
  -> timed-text formatter
```

Preserve:
- meaning
- tone/register
- character voice
- jokes/punchlines and reveal order
- names/terminology continuity across episodes

When text must be shortened for reading speed, prefer in this order:
1. re-time safely
2. re-segment/merge/split cues
3. remove redundant/paralinguistic material if not important
4. concise reformulation preserving register/meaning
5. deeper condensation only as a last resort

Every semantic edit should remain traceable to `text_raw`.

## 6. Broadcast QC cross-check

Netflix CPS is not the only useful readability measure. Ofcom guidance for pre-recorded television historically treats roughly 160–180 words/minute as the normal upper range and notes that >200 WPM becomes difficult for many viewers. Treat WPM as a warning metric, not as a replacement for locale/platform CPS rules.

Reference:
- https://www.ofcom.org.uk/siteassets/resources/documents/tv-radio-and-on-demand/broadcast-guidance/tv-access-services/tv-access-services.pdf

## 7. Deterministic QC pipeline

Run non-semantic fixes in a stable order so results are reproducible:

```text
normalize encoding/whitespace
  -> validate timestamps/order/overlap
  -> clause-aware segmentation
  -> line breaking
  -> min/max duration and gap rules
  -> shot-aware snapping/chaining
  -> CPS + WPM + line-count/CPL checks
  -> OCR/face collision-aware placement decision
  -> SDH density / speaker-label checks
  -> render SRT
  -> playback/profile validation
```

Safe auto-fixes must never silently change dialogue meaning.

Recommended issue fields:
- `code`
- `severity` (`error`, `warning`, `info`)
- `segment_id`
- `message`
- `metric_value`
- `limit`
- `autofix_safe`
- `before`
- `after`

Add at least these QC checks:
- chars per line
- max lines
- CPS
- WPM
- min/max duration
- overlap / negative duration
- inter-cue gap
- cue crossing a shot without crossing dialogue
- audio onset lag
- orphan/unbalanced line break heuristic
- duplicate consecutive text
- redundant forced narrative
- excessive repeated speaker labels
- unknown/low-confidence proper name
- collision with plot-relevant on-screen text
- excessive placement switching inside one shot/sequence

## 8. Validation / interoperability

Borrow the EBU approach of validators and processing nodes: each transformation should be independently inspectable and testable.

Relevant EBU resources remain useful as architectural prior art:
- EBU-TT-D: https://tech.ebu.ch/publications/tech3380
- EBU-TT Live toolkit: https://github.com/ebu/ebu-tt-live-toolkit
- EBU Timed Text schemas: https://github.com/ebu/ebu-tt-d-xsd

For the active SRT path, add:
- golden fixtures for accented French, overlapping speakers, music, forced narrative and shot-change timing
- Jellyfin-compatible positioning fixtures (`{\an8}` / bottom fallback)
- tests proving unsupported positioning tags do not alter dialogue text
- collision/placement debug-evidence tests
- playback smoke tests when a Jellyfin/Android TV test environment is available

## 9. Non-negotiable project rules

- raw evidence is immutable
- unknown is better than a confident-looking false label
- formatters cannot invent semantic content
- expensive computation is gated by cheap evidence
- timing decisions use audio *and* edit/shot structure
- SRT is the primary playback output
- IMSC/TTML remains inactive unless explicitly re-enabled
- local benchmark/QC reports are authoritative over guessed performance
