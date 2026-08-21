# SDH style guide for `subtitle-fusion`

This project targets **SDH/captions**, not only plain dialogue subtitles.

## Design principles

1. Preserve meaning before style.
2. Do not reveal narrative information too early.
3. Identify the speaker only when needed for clarity.
4. Prefer the **character name** over the actor name in subtitle output.
5. Keep diarization separate from character identification.
6. Keep raw ASR text and corrected text separate.
7. Preserve overlapping-speaker evidence instead of forcing all speech into a single speaker.
8. Add non-speech audio only when it is plot-pertinent, tonally relevant, or necessary for understanding.

## Diarization and speaker identity

Diarization answers:

> **Who spoke when?**

It should produce stable episode-local identities such as `SPEAKER_01`, `SPEAKER_02`, etc., along with speaker-turn boundaries and overlap regions.

Character identification answers a different question:

> **Which character does this voice belong to?**

Keep these separate in the internal evidence model:

```text
speaker_id = SPEAKER_03
speaker_identity_candidate = Muriel
speaker_identity_confidence = 0.94
```

A high-confidence diarization cluster does not prove that the speaker is a specific character. Character identity must be resolved using independent evidence such as OCR/name cards, visible context, title/episode candidates, dialogue context, previously validated speaker mappings and optional visual/face hints.

### Recommended diarization evidence

Preserve, where available:

- speaker-turn start/end timestamps
- stable episode-local speaker ID
- speaker-change boundaries
- overlap regions
- diarization confidence/quality signal
- optional speaker embedding/reference ID

### Fast/slow behavior

Diarization follows the same selective-compute policy as the rest of the project:

- fast whole-episode VAD/speaker-change/embedding pass
- accept clean single-speaker turns directly
- refine only ambiguous boundaries, rapid exchanges, overlaps or identity conflicts
- never re-diarize the entire episode merely because a few regions are difficult

## Speaker identification rules

### When to show the speaker name
Show a speaker identifier when the speaker cannot be reliably identified from the image alone, especially when the voice is:
- off-screen
- in another room
- on the phone / radio / intercom
- voice-over or narration
- part of a fast multi-speaker exchange
- overlapping with another speaker
- otherwise ambiguous

Diarization helps determine whether a speaker actually changed, whether two voices overlap, and whether an off-screen voice is consistent with a previously validated character.

### When not to show the speaker name
Do not add a speaker identifier when the active speaker is obvious on screen and there is no ambiguity.

A diarized `SPEAKER_03` label is internal metadata; it should not automatically appear in the visible subtitle.

### Which name to use
Use this priority order:
1. name explicitly shown on screen by OCR
2. character name confirmed by title/episode context and/or a validated speaker mapping
3. stable descriptive label such as `[homme]`, `[femme]`, `[voix masculine]`, `[voix féminine]`
4. numbered generic labels if needed, such as `[homme 1]`, `[homme 2]`

Never use an actor name in the visible subtitle unless the content itself identifies the actor rather than the character.

### Avoid spoilers
If the narrative has not revealed a name yet, do not invent or expose it.
Use a neutral label such as `[homme]`, `[femme]` or `[voix féminine]` until the content reveals the name.

A backend may already have resolved `SPEAKER_03 -> Muriel`; the renderer must still remain spoiler-safe and avoid showing `Muriel` before the story has established that identity for the viewer.

## Overlapping speakers

Overlaps must remain explicit evidence in the internal timeline.

Do not silently flatten:

```text
SPEAKER_01 + SPEAKER_02
```

into one speaker merely because ASR produced one mixed segment.

Depending on the output format and style rules, an overlap can be handled by:

- splitting the dialogue into separate subtitle events when timing permits
- using speaker labels when identity is required for clarity
- using richer ASS positioning/styling where appropriate
- sending the local region to a stronger diarization/ASR review path when speaker attribution is uncertain

The visible result should stay readable; preserving overlap evidence does not mean overloading the viewer with technical speaker IDs.

## Formatting policy

### Default output style
Preferred internal style for this project:
- speaker label in square brackets for SDH metadata, for example `[Morel]`
- generic French labels in square brackets and lowercase, for example `[voix masculine]`
- visible subtitle rendering may omit the label entirely when the active speaker is obvious

Examples:
- `[Morel] On verrouille tout.`
- `[voix masculine] Ouvrez la porte.`
- `[narrateur] Il était une fois...`

### Music and sound effects
Include sound effects only when they are:
- plot-pertinent
- necessary to follow scene changes
- part of tone, suspense, or humor
- not fully inferable from the image

Examples:
- `[porte qui claque]`
- `[pas discrets qui approchent]`
- `[musique tendue]`
- `[téléphone qui vibre]`

Avoid describing obvious visible actions as sound labels unless the sound matters.

### Song handling
If lyrics are important and intelligible:
- subtitle the lyrics
- keep song title / identification in metadata or separate SDH labels unless the active style requires visible identification

If music matters but lyrics do not:
- prefer a short label such as `[chanson mélancolique]`

### Hesitations and vocal texture
Prefer transcribing the hesitation in the dialogue when possible:
- `Je... je ne sais pas.`

Use labels only when that better conveys the scene:
- `[hésite]`
- `[chuchote]`
- `[crie]`

## Decision rules for the pipeline

### Auto-correct a name only if
- ASR confidence is low or the token is marked uncertain
- and at least one strong external clue exists
- and no stronger contradictory clue exists

A stable speaker mapping may support a correction, but diarization alone is not sufficient evidence for a character name.

### Evidence priority
1. OCR explicit on-screen text
2. title/episode-restricted IMDb character match
3. names already validated in the current show/episode glossary
4. dialogue context
5. validated speaker-to-character continuity
6. actor/face hint
7. phonetic similarity

### Output/debug fields
Each segment should preserve or be able to reference:
- `text_raw`
- `text_corrected`
- `speaker_id`
- `diarization_confidence`
- overlap metadata
- `speaker_identity_candidate`
- `speaker_identity_confidence`
- `decision.status`
- `decision.final_label`
- `decision.reasons`
- `decision.fusion_score`

## Recommended rendering behavior

### SRT
For broad compatibility, render only the semantic result needed by the viewer:
- `[Morel] On verrouille tout.` when identification is needed
- `On verrouille tout.` when the visible speaker is obvious
- `[porte qui claque]`

Do not expose raw labels such as `SPEAKER_03` in normal final SRT output.

### ASS
For richer styling, keep label and dialogue separable by style and allow overlap/positioning information to be represented more cleanly when needed.

## Examples

### Off-screen identified speaker
Raw ASR:
- `Murel, on verrouille tout.`

Evidence:
- diarization: `SPEAKER_03`
- OCR hit: `Commissaire Morel`
- IMDb character: `Commissaire Morel`
- previously validated mapping: `SPEAKER_03 -> Morel`

Output when identification is required:
- `[Morel] On verrouille tout.`

### Visible identified speaker
The same `SPEAKER_03 -> Morel` mapping exists, but Morel is clearly visible speaking.

Output:
- `On verrouille tout.`

### Unrevealed speaker
Backend identity candidate:
- `SPEAKER_04 -> Muriel`

Story has not revealed her identity yet.

Output:
- `[voix féminine] Il faut partir.`

### Overlapping speakers
Diarization:
- `SPEAKER_01 + SPEAKER_02` overlap for 1.2 seconds

Policy:
- preserve the overlap in debug/evidence data
- use labels/splitting/ASS positioning only when required for comprehension
- escalate attribution if ASR or speaker identity is uncertain

### Narration
- `[narrateur] La ville ne dormait jamais.`

### Audible but visible action
If the image already makes it obvious and the sound adds no extra value, omit the sound label.

## Source alignment
This style guide is intentionally aligned with widely used guidance such as:
- DCMP Captioning Key on quality and speaker identification
- Netflix SDH/timed-text guidance on speaker IDs, sounds, and use only when visual identification is insufficient

See also:
- `docs/FAST_SCOUT_PIPELINE.md` for diarization as a first-class evidence stream and selective refinement
- `docs/NETFLIX_FR_STYLE.md` for French Netflix-style output constraints
