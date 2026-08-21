# Netflix French (France) subtitle / SDH profile

This project applies a Netflix-style French (France) profile to generated subtitles. It is intended to make Jellyfin-facing SRT/ASS output follow Netflix timed-text conventions as closely as possible. It is **not** a claim that the generated files are an official Netflix delivery package; Netflix delivery formats and partner delivery specifications are separate from style compliance.

Official references:

- General requirements: https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements
- Subtitle timing: https://partnerhelp.netflixstudios.com/hc/en-us/articles/360051554394-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines
- French (France): https://partnerhelp.netflixstudios.com/hc/en-us/articles/217351577-French-France-Timed-Text-Style-Guide

## Enforced automatically

The runtime profile in `config/style_rules.yaml` currently enforces or checks:

- maximum 42 visible characters per line
- maximum 2 lines per subtitle event
- syntactic line breaking with a preference for a bottom-heavy two-line shape
- no silent truncation or paraphrasing when a subtitle cannot fit
- minimum event duration of 5/6 second
- maximum event duration of 7 seconds
- preferred French subtitle reading speed target of 17 characters/second
- French SDH ceiling of 20 characters/second
- minimum gap of 2 frames, using the configured frame rate
- chaining of short gaps below half a second to a 2-frame gap when safe
- a machine-readable `output.netflix-report.json` containing remaining violations

The formatter may adjust line breaks and may safely extend subtitle out-times. It does not shorten or paraphrase dialogue merely to satisfy a metric. Text reduction remains a semantic editorial operation and must go through the review/correction layer.

## French SDH conventions used by the project

The project-level policy follows the French guide in particular for:

- speaker IDs and sound effects in square brackets
- generic speaker and sound labels in lowercase, except proper names
- speaker IDs only when the speaker cannot otherwise be identified clearly
- character names rather than actor names in visible subtitle text
- spoiler-safe naming: do not reveal a character name before the story has established it
- plot-pertinent sound effects rather than descriptions of visible actions
- music descriptions based on genre and mood when a track identity is uncertain
- proper names kept in their approved/source form rather than translated
- accents and diacritics preserved in proper names

## Important timing notes

Netflix timing is not only a duration problem. The official guide expects timings to follow audio and shot changes. The current implementation handles duration and subtitle-to-subtitle gaps, but shot-change-aware timing still requires a scene-cut detector to be wired into the pipeline.

Planned timing refinement:

1. detect shot boundaries
2. align in-times/out-times within the Netflix half-second shot-change window
3. avoid subtitles hanging across scene changes unless dialogue genuinely crosses the cut
4. preserve the 2-frame inter-subtitle gap after retiming

## Quality and semantic review

A subtitle can be mechanically compliant and still be linguistically wrong. Netflix-style output therefore remains downstream of ASR, proper-name resolution, translation, contextual review, grammar/spelling correction and SDH enrichment. Mechanical formatting must never overwrite raw ASR evidence or invent content.
