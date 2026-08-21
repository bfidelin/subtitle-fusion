from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AudioEvent:
    label: str
    score: float
    start: float
    end: float
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrackCandidate:
    provider: str
    title: str | None = None
    artist: str | None = None
    confidence: float | None = None
    lyrics_overlap: float | None = None
    fingerprint_score: float | None = None
    mood_match: float | None = None
    vocal_match: bool | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MusicWindow:
    start: float
    end: float
    present: bool = False
    vocal: bool | None = None
    mood: str | None = None
    track_candidates: list[TrackCandidate] = field(default_factory=list)
    lyrics_text: str | None = None
    lyrics_confidence: float | None = None
    source_separation: str | None = None


class AudioEventProvider:
    def detect_events(self, audio_path: Path) -> list[AudioEvent]:
        raise NotImplementedError


class MusicAnalysisProvider:
    def detect_music_windows(self, audio_path: Path) -> list[MusicWindow]:
        raise NotImplementedError


class StubAudioEventProvider(AudioEventProvider):
    def detect_events(self, audio_path: Path) -> list[AudioEvent]:
        _ = audio_path
        return []


class PannsAudioEventProvider(AudioEventProvider):
    """AudioSet verifier for candidate audio windows/files.

    Keep this behind a cheap scout in production. Dependencies are imported lazily
    so core tests/agents do not need CUDA or the PANNs stack.
    """

    def __init__(
        self,
        *,
        device: str = "cuda",
        min_event_score: float = 0.68,
        window_seconds: float = 2.0,
        hop_seconds: float = 1.0,
        labels_allowlist: list[str] | None = None,
    ) -> None:
        self.device = device
        self.min_event_score = min_event_score
        self.window_seconds = window_seconds
        self.hop_seconds = hop_seconds
        self.labels_allowlist = set(labels_allowlist or [])

    def detect_events(self, audio_path: Path) -> list[AudioEvent]:
        try:
            import librosa
            import numpy as np
            from panns_inference import AudioTagging, labels
        except ImportError as exc:
            raise RuntimeError(
                "PANNs dependencies are missing. Install subtitle-fusion[audio]."
            ) from exc

        sample_rate = 32_000
        audio, _ = librosa.load(str(audio_path), sr=sample_rate, mono=True)
        model = AudioTagging(checkpoint_path=None, device=self.device)
        window = max(1, int(self.window_seconds * sample_rate))
        hop = max(1, int(self.hop_seconds * sample_rate))
        raw_events: list[AudioEvent] = []

        for offset in range(0, max(1, len(audio)), hop):
            chunk = audio[offset : offset + window]
            if len(chunk) < sample_rate // 4:
                break
            if len(chunk) < window:
                chunk = np.pad(chunk, (0, window - len(chunk)))
            clipwise, _ = model.inference(chunk[None, :])
            start = offset / sample_rate
            end = min(len(audio) / sample_rate, start + self.window_seconds)
            for index, score in enumerate(clipwise[0]):
                value = float(score)
                if value < self.min_event_score:
                    continue
                label = str(labels[index])
                if self.labels_allowlist and label not in self.labels_allowlist:
                    continue
                raw_events.append(
                    AudioEvent(
                        label=label,
                        score=value,
                        start=start,
                        end=end,
                        meta={"provider": "panns"},
                    )
                )

        return merge_adjacent_events(raw_events, max_gap=self.hop_seconds * 1.25)


class StubMusicAnalysisProvider(MusicAnalysisProvider):
    def detect_music_windows(self, audio_path: Path) -> list[MusicWindow]:
        _ = audio_path
        return []


def merge_adjacent_events(
    events: list[AudioEvent], *, max_gap: float = 1.25
) -> list[AudioEvent]:
    if not events:
        return []
    merged: list[AudioEvent] = []
    for event in sorted(events, key=lambda item: (item.label, item.start, item.end)):
        if (
            merged
            and merged[-1].label == event.label
            and event.start <= merged[-1].end + max_gap
        ):
            merged[-1].end = max(merged[-1].end, event.end)
            merged[-1].score = max(merged[-1].score, event.score)
        else:
            merged.append(event)
    return sorted(merged, key=lambda item: (item.start, item.end, item.label))


def build_audio_event_provider(config: str | dict[str, Any]) -> AudioEventProvider:
    if isinstance(config, str):
        name = config.lower()
        cfg: dict[str, Any] = {}
    else:
        cfg = config
        if not bool(cfg.get("enabled", True)):
            return StubAudioEventProvider()
        name = str(cfg.get("provider", "stub")).lower()

    if name in {"stub", "none", "disabled", "yamnet"}:
        # YAMNet is the intended cheap scout but is not wired in this adapter yet.
        return StubAudioEventProvider()
    if name != "panns":
        raise ValueError(f"Unsupported audio event provider: {name}")
    return PannsAudioEventProvider(
        device=str(cfg.get("device", "cuda")),
        min_event_score=float(cfg.get("min_event_score", 0.68)),
        window_seconds=float(cfg.get("window_seconds", 2.0)),
        hop_seconds=float(cfg.get("hop_seconds", 1.0)),
        labels_allowlist=list(cfg.get("labels_allowlist", [])),
    )


def build_music_analysis_provider(name: str) -> MusicAnalysisProvider:
    _ = name
    return StubMusicAnalysisProvider()
