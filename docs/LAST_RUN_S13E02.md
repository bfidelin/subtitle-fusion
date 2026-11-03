# S13E02 – results of last production run

## Pipeline mode
- fast: ASR + OCR parallel
- diarization: none
- diffus processed: Whisper Turbo + context corrections + candidates

## Metrics
- SRT cues: 1267
- generated words: 7644
- reference words: 8521 (when reachable)
- WER: 17.53 %
- CER: 14.49 %

## Confidence / gating
- ASR model: `large-v3-turbo`
- conditions: `beam_size=5`, `best_of=5`, `temperature=0.0`
- word probabilities are available in JSON

## OCR context
- hits: 23 / 23 unique
- usable OCR candidates: yes
- samples: JAMES, FRASER, CHIEF STEW, Azur, Rainbow, Moe

## People context
- Jellyfin rows loaded: 243
- candidates injected with min 30 s: 50

## Corrections
- context terms / candidate fusion / normalization
- no `- SPEAKER n`
- Netflix style applied (duration/wrapping/time)
- `proper_noun_candidate` heuristic flagged

## Diff summary
Counts: 7169 hits, 136 insertions, 1018 deletions, 334 substitutions
Examples: Blow Deck -> Below Deck; insertions (you, i, the, decor); deletions (you, to, yeah, a, i, the); subs (gonna to, going->gonna, ok/okay, a->astern, got->gotta)