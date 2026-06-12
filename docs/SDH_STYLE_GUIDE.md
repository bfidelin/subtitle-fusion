# SDH style guide for `subtitle-fusion`

This project targets **SDH/captions**, not only plain dialogue subtitles.

## Design principles

1. Preserve meaning before style.
2. Do not reveal narrative information too early.
3. Identify the speaker only when needed for clarity.
4. Prefer the **character name** over the actor name in subtitle output.
5. Keep raw ASR text and corrected text separate.
6. Add non-speech audio only when it is plot-pertinent, tonally relevant, or necessary for understanding.

## Speaker identification rules

### When to show the speaker name
Show a speaker identifier when the speaker cannot be reliably identified from the image alone, especially when the voice is:
- off-screen
- in another room
- on the phone / radio / intercom
- voice-over or narration
- part of a fast multi-speaker exchange
- otherwise ambiguous

### When not to show the speaker name
Do not add a speaker identifier when the active speaker is obvious on screen and there is no ambiguity.

### Which name to use
Use this priority order:
1. name explicitly shown on screen by OCR
2. character name confirmed by title/episode context
3. stable descriptive label such as `[man]`, `[woman]`, `[male voice]`, `[female voice]`
4. numbered generic labels if needed, such as `[man 1]`, `[man 2]`

Never use an actor name in the visible subtitle unless the content itself identifies the actor rather than the character.

### Avoid spoilers
If the narrative has not revealed a name yet, do not invent or expose it.
Use a neutral label such as `[man]` or `[woman]` until the content reveals the name.

## Formatting policy

### Default output style
Preferred internal style for this project:
- speaker label in square brackets for SDH metadata, for example `[Morel]`
- visible subtitle rendering may convert this to `Morel:` for SRT if configured

Examples:
- `[Morel] On verrouille tout.`
- `[male voice] Open the door.`
- `[narrator] Once upon a time...`

### Music and sound effects
Include sound effects only when they are:
- plot-pertinent
- necessary to follow scene changes
- part of tone, suspense, or humor
- not fully inferable from the image

Examples:
- `[door slams]`
- `[quiet footsteps approaching]`
- `[tense music builds]`
- `[phone vibrating]`

Avoid describing obvious visible actions as sound labels unless the sound matters.

### Song handling
If lyrics are important and intelligible:
- subtitle the lyrics
- keep song title / identification in metadata or separate SDH labels

If music matters but lyrics do not:
- prefer a short label such as `[melancholic song playing]`

### Hesitations and vocal texture
Prefer transcribing the hesitation in the dialogue when possible:
- `I... I don't know.`

Use labels only when that better conveys the scene:
- `[hesitates]`
- `[whispers]`
- `[shouting]`

## Decision rules for the pipeline

### Auto-correct a name only if
- ASR confidence is low or the token is marked uncertain
- and at least one strong external clue exists
- and no stronger contradictory clue exists

### Evidence priority
1. OCR explicit on-screen text
2. title/episode-restricted IMDb character match
3. dialogue context
4. actor/face hint
5. phonetic similarity

### Output fields
Each segment should preserve:
- `text_raw`
- `text_corrected`
- `decision.status`
- `decision.final_label`
- `decision.reasons`
- `decision.fusion_score`

## Recommended rendering behavior

### SRT
For broad compatibility, render:
- `Morel: On verrouille tout.`
- `[door slams]`

### ASS
For richer styling, keep label and dialogue separable by style.

## Examples

### Off-screen identified speaker
Raw ASR:
- `Murel, on verrouille tout.`

Fusion result:
- OCR hit: `Commissaire Morel`
- IMDb character: `Commissaire Morel`
- Output: `Morel: On verrouille tout.`

### Unrevealed speaker
- Output: `[male voice] We need to leave now.`

### Narration
- Output: `[narrator] The city never slept.`

### Audible but visible action
If the image already makes it obvious and the sound adds no extra value, omit the sound label.

## Source alignment
This style guide is intentionally aligned with widely used guidance such as:
- DCMP Captioning Key on quality and speaker identification
- Netflix SDH/timed-text guidance on speaker IDs, sounds, and use only when visual identification is insufficient
