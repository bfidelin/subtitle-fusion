# Useful videos

Last verified: **2026-08-21**.

This is the short video index for `subtitle-fusion`. Keep technical benchmark sources in `docs/PERFORMANCE_REFERENCES.md`; use this page when you want to quickly understand a component or show an agent which demo is worth watching.

## ASR / diarization

### Faster-Whisper CPU/GPU benchmark
https://www.youtube.com/watch?v=Kyc0AgMIBSU

Useful for:
- install/runtime expectations
- CPU vs GPU behavior
- batching/performance intuition

### WhisperX speaker/timestamp demo
https://www.youtube.com/watch?v=zY-8Sr-FzIw

Useful for:
- word timestamps
- alignment
- speaker attribution flow

### pyannote talk
https://www.youtube.com/watch?v=CtjDotATEI0

Useful for:
- diarization concepts
- speaker turns
- embeddings and clustering intuition

## Audio events / music

### YAMNet demo/tutorial
https://www.youtube.com/watch?v=DLVA10sb1iE

Useful for:
- cheap AudioSet-class scouting
- broad event classification
- candidate-window routing before a stronger verifier

### PANNs demos
https://www.youtube.com/watch?v=QyFNIhRxFrY

https://www.youtube.com/watch?v=7TEtDMzdLeY

Useful for:
- AudioSet event classification
- stronger verification of candidate windows
- understanding why PANNs belongs after a cheap scout rather than on every window

### Demucs source separation
https://www.youtube.com/watch?v=BttaeQaO80E

Canonical code repository:
https://github.com/adefossez/demucs

Useful for:
- vocal/instrument separation
- isolating vocals only on selected music windows
- understanding the Demucs/HTDemucs workflow

Status note: the canonical repository is now `adefossez/demucs`; the old `facebookresearch/demucs` repository is archived. As of 2026-08-21 this is still Demucs v4 / Hybrid Transformer Demucs, not a v5 release.

## Active speaker

### TalkNet ASD demo
https://www.youtube.com/watch?v=a7rLzt2ZWk0

Useful for:
- active-speaker detection intuition
- understanding the visual/audio association problem

For implementation, `subtitle-fusion` currently prefers benchmarking LR-ASD before TalkNet because the active-speaker path must remain sparse and lightweight.

## Maintenance rule

When adding a video:
- state what it teaches or demonstrates
- distinguish tutorial/demo from benchmark evidence
- keep the canonical project/repository link beside it
- update `docs/PERFORMANCE_REFERENCES.md` when the video is also used to support a performance claim
