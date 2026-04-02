from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Word:
    text: str
    start: float
    end: float
    confidence: float | None = None
    flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OCRHit:
    text: str
    time: float
    confidence: float | None = None
    bbox: tuple[int, int, int, int] | None = None


@dataclass(slots=True)
class Candidate:
    type: str
    name: str
    score: float
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Event:
    label: str
    score: float


@dataclass(slots=True)
class MusicInfo:
    present: bool = False
    track: str | None = None
    lyrics_detected: bool = False


@dataclass(slots=True)
class Decision:
    status: str
    final_text: str
    final_label: str | None
    fusion_score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Segment:
    id: int
    start: float
    end: float
    speaker_id: str
    text_raw: str
    words: list[Word] = field(default_factory=list)
    speaker_name_candidate: str | None = None
    character_candidate: str | None = None
    actor_candidate: str | None = None
    text_corrected: str | None = None
    ocr_hits: list[OCRHit] = field(default_factory=list)
    imdb_candidates: list[Candidate] = field(default_factory=list)
    vision_candidates: list[Candidate] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    music: MusicInfo = field(default_factory=MusicInfo)
    decision: Decision | None = None

    def final_text(self) -> str:
        return self.text_corrected or self.text_raw


@dataclass(slots=True)
class MediaContext:
    title: str | None = None
    season: int | None = None
    episode: int | None = None
    imdb_title_id: str | None = None
    duration_sec: float | None = None


@dataclass(slots=True)
class PipelineResult:
    media: MediaContext
    segments: list[Segment]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
