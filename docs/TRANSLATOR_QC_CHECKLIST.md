# Translator and subtitle QC checklist

Last verified: **2026-08-21**.

This checklist turns professional subtitle/translation practice into explicit, testable stages for `subtitle-fusion`. It complements `STANDARDS_AND_PRACTICES.md`; it is not a replacement for the active platform/locale profile.

## 1. Production order

Do not ask one model to "make the subtitles good" in a single opaque pass. Use a staged workflow:

```text
source evidence
  -> transcription / source-template selection
  -> timing / segmentation
  -> terminology + proper-name preparation
  -> translation candidate
  -> semantic review
  -> grammar / spelling / punctuation review
  -> reading-speed + line-break adaptation
  -> SDH / forced-narrative review
  -> shot-aware timing pass
  -> final watch-through / QC report
```

Every semantic stage must preserve a trace back to `text_raw` and the source cue.

## 2. Before translating

Collect the best available context first:
- existing subtitle/template track when trustworthy
- title, episode and season metadata
- character list and approved spellings
- recurring show glossary
- previously validated voiceprint/character mappings
- plot-relevant OCR names/locations
- source-language transcript and word timings
- visible speaker/shot context when it changes meaning

Do not translate a proper noun blindly when OCR, episode metadata or a known glossary can resolve it first.

## 3. Semantic translation review

For each cue, check:
- meaning preserved
- no invented information
- no omitted plot-relevant information
- speaker intent preserved
- register preserved (formal, slang, vulgar, child speech, dialect, technical language)
- joke/punchline timing preserved
- reveal order preserved
- pronouns and grammatical gender consistent with known context
- ambiguity preserved when the source is deliberately ambiguous
- recurring terminology consistent across the episode/season

A fluent rewrite is still wrong if it changes character voice, implication or reveal timing.

## 4. Proper names and terminology

Maintain a show/season glossary with at least:
- canonical source form
- approved localized form, if any
- aliases/nicknames
- pronunciation/phonetic hints when useful for ASR correction
- first-known/reveal timestamp or episode when spoiler-safe naming matters
- confidence/source for the decision

Evidence priority for uncertain names:
1. explicit on-screen text / credits / title cards
2. trusted embedded subtitle/template
3. episode/title-scoped metadata
4. validated show glossary
5. speaker/character continuity
6. dialogue context
7. phonetic similarity alone

Never promote a low-confidence phonetic guess to a canonical name without stronger evidence.

## 5. Grammar, spelling and punctuation review

Run this after semantic translation, not before.

Check:
- spelling and accents/diacritics
- punctuation appropriate to the locale/profile
- apostrophes/quotation marks/dashes
- sentence agreement and tense consistency
- repeated words caused by ASR overlap
- accidental homophones
- casing of proper nouns and SDH labels
- numbers, dates, measurements and abbreviations
- ellipsis/interruption semantics

Automatic proofreading may fix unambiguous orthographic issues. Rewrites that can alter meaning require semantic review and traceability.

## 6. Subtitle segmentation and line breaking

Raw ASR segmentation is not final subtitle segmentation.

Prefer breaks at:
- sentence boundaries
- clauses
- punctuation
- meaningful pauses
- speaker changes

Avoid splitting tightly bound units when possible:
- article + noun
- pronoun + verb
- preposition + complement
- adjective + noun
- first name + surname
- auxiliary + participle/infinitive

For two lines, prefer balanced or bottom-heavy shapes only when linguistically natural. Never optimize visual balance at the cost of syntax.

## 7. Reading speed

Check both **CPS** and **WPM**.

For the Netflix-style fr-FR profile currently used by the project:
- 42 visible characters maximum per line
- 2 lines maximum
- 17 CPS normal target
- 20 CPS SDH ceiling/profile warning
- minimum 20 frames
- maximum 7 seconds

WPM is a complementary warning metric, especially for dense short-word dialogue. Ofcom guidance is useful as a broadcast cross-check; it is not a substitute for the active locale/platform profile.

When a cue is too dense, prefer this order:
1. safely extend timing
2. split/resegment
3. merge with an adjacent cue if it improves readability and timing
4. remove redundant non-semantic material
5. concise semantic reformulation
6. deeper condensation only as a reviewed last resort

Never silently delete meaning just to make a metric green.

## 8. Timing and shot changes

Timing uses both speech and edit structure.

Check:
- in-time close to speech onset
- out-time long enough to read but not hanging unnecessarily
- minimum inter-cue gap
- no negative/overlapping cues unless the format/semantics explicitly require it
- no cue lingering over a cut without a good reason
- dialogue genuinely crossing a cut may keep a crossing cue
- punchline/reveal must not appear before the corresponding audio/visual beat

The shared shot map should be computed once and reused for subtitle timing, OCR sampling and active-speaker/face tracking.

## 9. SDH review

Add only accessibility information that changes understanding.

Check:
- speaker labels only when identity is not otherwise clear
- do not repeat established speaker names needlessly
- prefer character names over actor names
- do not reveal a character name before the story does
- meaningful sounds only; do not narrate obvious visible action
- music description only when narratively useful
- lyrics only when intelligible/relevant and legally/operationally appropriate
- identify a known foreign language when useful rather than using a vague label

Keep `speaker_id`, character identity and visual visibility separate. A face-detector miss does not prove off-screen speech.

## 10. On-screen text / forced narrative

OCR is evidence, not automatically a subtitle.

For each candidate on-screen text item:
- is it plot-pertinent?
- is it already conveyed by dialogue?
- is it readable without a subtitle?
- does it conflict with dialogue subtitle bandwidth?
- should it be translated, transliterated, preserved or omitted?

Suppress redundant forced narrative. Preserve the OCR raw string, crop/timing and confidence in debug evidence.

## 11. Existing subtitle/template reuse quality gate

A found embedded text track is a **candidate reference**, not automatically truth.

Score at least:
- language match
- coverage of the program
- cue count/density sanity
- timestamp monotonicity and overlap rate
- global sync fit against VAD/audio
- sampled lexical/ASR agreement
- signs of hearing-impaired/SDH vs dialogue-only content
- signs of wrong edit/version

Recommended routing:

```text
high quality + good sync
  -> reuse timing/text as primary reference and enrich

high quality text + simple global offset/drift
  -> repair sync, then enrich

piecewise mismatch / alternate edit
  -> piecewise alignment

low quality / wrong language / incomplete
  -> WhisperX baseline, keep track only as secondary evidence
```

Do not let a low-quality subtitle track suppress a better ASR result.

## 12. Final watch-through / automated proxy

Human professional workflows end with a watch-through. For automation, emulate this with an evidence-driven final pass and a machine-readable QC report.

At minimum flag:
- unresolved low-confidence names
- semantic reviewer disagreement
- spelling/grammar warnings
- CPS/WPM violations
- line-length/line-count violations
- suspicious cue gaps/overlaps
- shot-crossing warnings
- duplicated text
- repeated/unnecessary speaker labels
- redundant forced narrative
- untranslated/unknown-language fragments
- suspiciously long silence with displayed dialogue
- dialogue with no nearby speech evidence

The pipeline should prefer a visible warning/manual-review flag over an unsafe automatic correction.

## 13. Automation confidence model

Keep confidence dimensions separate rather than collapsing everything too early:
- ASR confidence
- alignment confidence
- diarization confidence
- speaker identity confidence
- OCR confidence
- proper-name confidence
- source/template quality
- sync fit quality
- translation semantic confidence
- grammar/spelling QA confidence
- final routing confidence

A high score in one dimension must not erase a contradiction in another.

## 14. Definition of done for one episode

An episode is production-ready only when:
- raw evidence remains available
- subtitle source/reference choice is recorded
- unresolved risky proper names are reviewed or flagged
- semantic translation review has no blocking issue
- grammar/spelling review has no blocking issue
- timing/layout profile passes or remaining violations are reported
- SDH/forced narrative is concise and relevant
- output renders correctly in target formats
- benchmark/QC report is written
- changes remain reproducible from the same inputs/config/model versions
