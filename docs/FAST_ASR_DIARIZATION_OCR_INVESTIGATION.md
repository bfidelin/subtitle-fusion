# Fast ASR, Diarization, OCR And Similarity Investigation

## Goal

Measure what can be brought to `subtitle-fusion` while staying fast:
- local Faster-Whisper `large-v3-turbo`
- local diarization (Sherpa CPU / Pyannote GPU)
- fast sparse OCR context (RapidOCR / PP-OCRv6 small)
- semantic but conservative subtitle correction

Core rule from repo docs remains:
- reuse evidence first
- scout cheaply
- spend expensive compute only when it can change the result
- never silently rewrite selected text

## Current baseline

Local ASR API:
- service: `whisper-asr.service` (`whisper_api_server.py`)
- host/port: `0.0.0.0:9000`
- engine: `faster_whisper`
- model: `large-v3-turbo`
- compute type: `int8_float16`
- batch size: 8
- batched pipeline enabled with VAD + word timestamps + transcribe task

Benchmarked E02 3-min audio (`banshee_3min.wav`):
- ASR Turbo batched (warm): 1.39 s
- ASR Turbo no word timestamps (warm): 46.1 s (sequential path)
- ASR `large-v3` default: 17 s for 3 min
- ASR `large-v3` sequential: 46.1 s for 3 min

## Diarization findings

### Sherpa ONNX (CPU)

- current implementation in `whisper_api_server.py`
- `OfflineSpeakerDiarization` uses pyannote segmentation + clustering + 3D-Speaker embeddings
- result:
  - 3 min Banshee audio: ~4.7-5.0 s, 4 speakers
  - 54 min Below Deck S13E02: ~190 s total when `diarize=true`
- Embedding extraction:
  - `SpeakerEmbeddingExtractor` with 512-dim embeddings
  - top-3 turns per speaker, averaged and L2-normalized
  - added to local API as `meta["speaker_embeddings"]`

### Pyannote community-1 (GPU)

Tested on RTX 5060 Ti 16 GB with HF token:
- 3 min audio: 4.34 s, 5 speakers
- 54 min audio: 80.4 s, 14 speakers
- VRAM peak: about 7.16 GiB allocated / 15.48 GiB total

So Pyannote GPU is significantly faster than Sherpa CPU, but still not under 30 s per episode.

### NeMo Sortformer (GPU)

Tested on same RTX 5060 Ti:
- 3 min audio: ~0.66 s, 4 speakers
- 43 min audio: OutOfMemory with current call; needs 90 s session chunking and label continuity before it can be used per episode
- no speaker embeddings directly
Conclusion: useful GPU diarization candidates exist, but none are a transparent drop-in under 30 s on full episodes.

## OCR findings

Fast OCR pipeline:
- `src/fast_ocr.py` uses sparse sampling + OpenCV VideoCapture + RapidOCR PP-OCRv6-small ONNX
- typical speed: about 0.19 s/frame in a real run
- best cost shape: stride sampling + confidence >= 0.7 + capped max 60 frames

Measured S13E02 (54 min), stride 5 s, 60 frames:
- elapsed: 11.49 s
- hits: 23 unique texts

Measured S13E03:
- elapsed full pipeline: 176.19 s
- OCR hits: 37 unique texts
- useful context: `MATT`, `ALEX`, `9:07 AM`, `FRASER`, `CHIEF`, etc.

Measured S13E04 (not a clean human reference, Whisper-generated existing SRT):
- full pipeline 178.97 s
- OCR hits: 46 unique texts

OCR rule:
- frame-diff/scene sampling first
- full-frame detection/OCR second
- crops + hash + temporal voting
- annotate, do not auto-correct automatically

## Similarity benchmark

Prior evaluator `eval_episodes.py` and local `compare_srt.py` benchmarked various configs:
- `large-v3-turbo` variants
- batch sizes 8/16
- f16/int8/int8_float16
- `distil-large-v3`

The HTTP provider default uses `large-v3-turbo`, `int8_float16`, batched Faster-Whisper.

Important metric caveat:
- comparing generated subtitles to existing `.srt` files must strip speaker labels, timestamps, braces, brackets, and parentheticals before WER
- the first bad comparison included `- SPEAKER n` labels and `{...}` tags, which heavily inflated WER

Corrected results:
- `S13E02` Whisper vs main `.srt`: 14.20 % WER / 10.97 % CER
- `S13E02` Whisper vs `.eng.srt`: 34.20 % WER / 28.17 % CER
- `S13E03` Whisper vs embedded English: 23.87 % WER
- `S13E04` Whisper vs existing `.srt`: 12.45 % WER / 8.81 % CER, but that existing SRT is itself Whisper-generated, so it is not a clean human reference

Example substitution classes:
- `going/gonna`
- `rainbeau/rainbow`
- `bosun/boson`
- `kerry/carry`
- `lime/lemon`
- insertions of filler words
- deletions of small tokens and punctuation/noise tags

## Identity and names

Possible proper nouns observed in S13E02:
- Alex, James, Matt, Rosa, Katie, Kerry, Kayleigh, Fraser, Rainbow, Moe

Possible proper nouns observed in S13E04:
- Alex, Matt, Rosa, Kerry, Kayleigh, James, Lily, Ethan, Robbie, Kat

Diarization over-segments (E02: 82 speaker clusters, E04: 73), so `SPEAKER_x` IDs are not reliable person identities. Better path:
1. embeddings + manual speaker map/enrollment
2. OCR/IMDb/voice context as candidates
3. conservative resolution

`imdb_index.py` can use local TSV files `data/imdb` to attach actor/character candidates, but no local IMDb data is currently present.

TVDB/Jellyfin/Sonarr credentials and metadata plumbing are available on this machine, but not yet wired into `subtitle-fusion`.

## Recommended strategy

Fast mode (<30 s):
- `providers.asr=whisper_http`
- `diarization=none`
- OCR sparse ON (stride 5 s, cap 60)
- confidence-based review flags
- Netflix style validation
- no identity enrichment

Identity / quality mode (~3+ min):
- `providers.asr=whisper_http`
- `diarization=whisper_http` (or `whisperx_pyannote` if available)
- local Sherpa embeddings first
- manual speaker map for enrollment
- OCR and IMDb as candidates
- resolve corrections conservatively
- pyannote can be tested later in an isolated env if exact person embeddings are required

## Files and runtime artifacts to reproduce

- integrated provider: `src/whisper_http_provider.py`
- embedded provider: `src/embedded_subtitle_provider.py`
- fast OCR: `src/fast_ocr.py`
- whisper server: `/home/calmos/scripts/whisper_api_server.py`
- ASR systemd unit: `/home/calmos/.config/systemd/user/whisper-asr.service`
- runtime outputs examples:
  - `/tmp/sf-par-s13e02/output.srt`
  - `/tmp/sf-ocrtst-s13e02/output.srt`
  - `/tmp/sf-ocrtst-s13e03/output.srt`
  - `/tmp/sf-ocr-s13e04/output.srt`

## Next actions

1. Make first-parties register/index candidates explicitly before fusion.
2. Add `proper_noun_candidate` heuristic on capitalized ASR words.
3. Implement OCR candidate type in fusion scoring.
4. Add Sonarr metadata fetch, then TVDB/IMDb where IDs are available.
5. Keep pyannote GPU as opt-in remote subprocess or isolated venv only.
