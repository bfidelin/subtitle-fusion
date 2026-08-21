# WhisperX + pyannote runtime

`subtitle-fusion` now has a first runtime adapter for WhisperX and pyannote.

The intent is to reuse the parts WhisperX already does well instead of rebuilding them:

- Faster-Whisper batched ASR
- VAD-aware transcription
- forced word alignment
- word-level timestamps/scores
- pyannote speaker diarization
- stable episode-local speaker labels
- speaker embeddings when requested
- word/segment speaker assignment

`subtitle-fusion` remains responsible for the higher-level fusion layer: OCR, proper names, speaker-to-character identity, confidence routing, selective re-ASR, music/lyrics, linguistic QA and Netflix/SDH rendering.

## Version policy

The optional dependency currently targets the stable WhisperX 3.8.x line:

```toml
whisperx>=3.8.6,<3.9
```

WhisperX itself brings `faster-whisper` and `pyannote-audio`. Keep it as an optional extra because it also constrains the PyTorch/CUDA stack and can be heavier than the core project.

Install with:

```bash
pip install -e ".[whisperx]"
```

For an existing GPU environment, inspect the resulting Torch/CUDA dependency plan before upgrading in place. A dedicated virtual environment is the safest initial validation path.

## Hugging Face access

The default diarization model is:

```text
pyannote/speaker-diarization-community-1
```

Before first use:

1. accept the model conditions on Hugging Face
2. create a read token
3. expose it as `HF_TOKEN`

Example:

```bash
export HF_TOKEN=hf_...
```

Never commit the real token.

## Configuration

`config/settings.yaml` now contains:

```yaml
providers:
  asr: whisperx
  diarization: whisperx_pyannote

whisperx:
  model: large-v3-turbo
  device: auto
  compute_type: float16
  batch_size: 16
  language: null
  vad_method: pyannote
  align: true
  diarize: true
  diarization_model: pyannote/speaker-diarization-community-1
  hf_token_env: HF_TOKEN
  min_speakers: null
  max_speakers: null
  return_embeddings: true
  fill_nearest_speaker: false
```

`device: auto` selects CUDA when Torch reports a CUDA device, otherwise CPU. On CPU, the adapter automatically avoids `float16` and falls back to `int8` compute.

## Runtime flow

```text
media file
   |
   v
WhisperX load_audio
   |
   +--> Faster-Whisper/VAD transcription
   |          |
   |          v
   |    language + segments
   |          |
   |          v
   |    forced word alignment
   |          |
   |          v
   |    word timestamps/scores
   |
   +--> pyannote Community-1 diarization
              |
              +--> speaker turns
              +--> speaker embeddings
              +--> overlaps retained as evidence
              |
              v
        assign_word_speakers
              |
              v
     subtitle-fusion models
              |
              +--> Segment.speaker_id
              +--> Word.speaker_id
              +--> PipelineResult.speaker_turns
              +--> PipelineResult.speaker_embeddings
              +--> Segment.overlap_speakers
```

## Important semantic boundary

Diarization and character identity stay separate.

```text
SPEAKER_02
```

means only that the voice cluster is believed to be the same speaker.

Later fusion may establish:

```text
SPEAKER_02 -> Muriel
speaker_identity_confidence = 0.96
```

using OCR, visible context, IMDb/show metadata, validated mappings and other evidence. A pyannote speaker ID must never be rendered directly as a character name.

## Overlapping speech

WhisperX itself documents overlapping speech as a difficult case. The adapter therefore preserves overlap evidence instead of pretending the attribution is certain.

When multiple diarization turns intersect one subtitle segment, `Segment.overlap_speakers` records all involved `SPEAKER_xx` IDs. This becomes an escalation trigger for the future selective review router.

## Word alignment limitations

WhisperX alignment can legitimately omit timestamps for tokens unsupported by the alignment model, such as some numeral/symbol forms. The adapter does **not** invent fake word timestamps. The segment text is preserved and unaligned tokens can later be routed for selective review.

## Current implementation status

Implemented now:

- lazy/optional WhisperX import
- automatic CUDA/CPU device selection
- Faster-Whisper transcription through WhisperX
- forced alignment
- pyannote Community-1 diarization
- optional min/max speaker hints
- speaker embeddings
- word and segment speaker assignment
- normalized `Word` confidence from WhisperX alignment scores
- stable `SpeakerTurn` data in debug JSON
- overlap detection/evidence
- provider selection from `config/settings.yaml`
- pure unit tests for normalization and overlap handling without requiring GPU models

Not implemented yet:

- calibrated diarization confidence values (WhisperX does not expose a simple per-turn confidence in its normalized dataframe)
- direct use of pyannote exclusive diarization output
- evidence timeline/router object joining ASR, speakers, OCR, shots and audio events
- selective local re-ASR based on confidence/conflicts
- speaker-to-character identity resolver
- persistence of speaker identity across episodes
- overlap-specific source separation/re-ASR
- end-to-end GPU integration test with a real fixture

## Why WhisperX is the baseline, not the whole architecture

Do not run Faster-Whisper separately and then run WhisperX over the same full episode a second time. WhisperX already uses Faster-Whisper internally. The baseline should be one whole-episode WhisperX pass for ASR/alignment/diarization, followed by `subtitle-fusion` selective processing only where evidence says it is useful.

The future fast scout (Moonshine), OCR detector, music classifier and shot detector remain independent parallel evidence sources. They should not trigger duplicate whole-episode Whisper passes.

## Upstream references

- WhisperX: https://github.com/m-bain/whisperX
- pyannote-audio: https://github.com/pyannote/pyannote-audio
- Community-1 diarization model: https://huggingface.co/pyannote/speaker-diarization-community-1
