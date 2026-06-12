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


class StubMusicAnalysisProvider(MusicAnalysisProvider):
    def detect_music_windows(self, audio_path: Path) -> list[MusicWindow]:
        _ = audio_path
        return []


def build_audio_event_provider(name: str) -> AudioEventProvider:
    _ = name
    return StubAudioEventProvider()


def build_music_analysis_provider(name: str) -> MusicAnalysisProvider:
    _ = name
    return StubMusicAnalysisProvider()
