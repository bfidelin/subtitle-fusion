from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.models import Segment


class DiarizationError(RuntimeError):
    pass


@dataclass(slots=True)
class SpeakerTurn:
    start: float
    end: float
    speaker_id: str


@dataclass(slots=True)
class DiarizationResult:
    turns: list[SpeakerTurn] = field(default_factory=list)
    speaker_embeddings: dict[str, list[float]] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


class DiarizationProvider:
    def diarize(self, audio_path: Path) -> DiarizationResult:
        raise NotImplementedError


class PyannoteDiarizationProvider(DiarizationProvider):
    def __init__(self, *, model: str = "pyannote/speaker-diarization-community-1", device: str = "cuda", token_env: str = "HUGGINGFACE_TOKEN", min_speakers: int | None = None, max_speakers: int | None = None, use_exclusive: bool = True, segmentation_batch_size: int | None = None, embedding_batch_size: int | None = None) -> None:
        self.model = model
        self.device = device
        self.token_env = token_env
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.use_exclusive = use_exclusive
        self.segmentation_batch_size = segmentation_batch_size
        self.embedding_batch_size = embedding_batch_size

    def diarize(self, audio_path: Path) -> DiarizationResult:
        try:
            import torch
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise DiarizationError("pyannote.audio is not installed. Install subtitle-fusion[diarization].") from exc

        token = os.getenv(self.token_env)
        if not token:
            raise DiarizationError(f"{self.token_env} is required for the gated pyannote model {self.model}")

        pipeline = Pipeline.from_pretrained(self.model, token=token)
        pipeline.to(torch.device(self.device))
        if self.segmentation_batch_size is not None and hasattr(pipeline, "segmentation_batch_size"):
            pipeline.segmentation_batch_size = self.segmentation_batch_size
        if self.embedding_batch_size is not None and hasattr(pipeline, "embedding_batch_size"):
            pipeline.embedding_batch_size = self.embedding_batch_size

        kwargs: dict[str, int] = {}
        if self.min_speakers is not None:
            kwargs["min_speakers"] = self.min_speakers
        if self.max_speakers is not None:
            kwargs["max_speakers"] = self.max_speakers
        output = pipeline(str(audio_path), **kwargs)

        annotation = (getattr(output, "exclusive_speaker_diarization", None) if self.use_exclusive else None) or getattr(output, "speaker_diarization", output)
        turns = [SpeakerTurn(float(turn.start), float(turn.end), str(speaker)) for turn, _, speaker in annotation.itertracks(yield_label=True)]

        embeddings: dict[str, list[float]] = {}
        matrix = getattr(output, "speaker_embeddings", None)
        labels = list(getattr(output, "speaker_diarization", annotation).labels())
        if matrix is not None:
            for index, speaker in enumerate(labels):
                if index >= len(matrix):
                    break
                embeddings[str(speaker)] = [float(value) for value in matrix[index].tolist()]
        return DiarizationResult(turns=turns, speaker_embeddings=embeddings, meta={"provider": "pyannote", "model": self.model})


class StubDiarizationProvider(DiarizationProvider):
    def diarize(self, audio_path: Path) -> DiarizationResult:
        _ = audio_path
        return DiarizationResult()


def overlap_seconds(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def speaker_for_interval(start: float, end: float, turns: list[SpeakerTurn]) -> str | None:
    best_speaker: str | None = None
    best_overlap = 0.0
    for turn in turns:
        overlap = overlap_seconds(start, end, turn.start, turn.end)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = turn.speaker_id
    return best_speaker


def assign_speakers(segments: list[Segment], turns: list[SpeakerTurn]) -> list[Segment]:
    for segment in segments:
        speaker = speaker_for_interval(segment.start, segment.end, turns)
        if speaker:
            segment.speaker_id = speaker
        for word in segment.words:
            word_speaker = speaker_for_interval(word.start, word.end, turns)
            if word_speaker:
                word.speaker_id = word_speaker
    return segments


def build_diarization_provider(config: dict[str, Any]) -> DiarizationProvider:
    name = str(config.get("provider", "pyannote")).lower()
    if name == "stub":
        return StubDiarizationProvider()
    if name != "pyannote":
        raise ValueError(f"Unsupported diarization provider: {name}")
    return PyannoteDiarizationProvider(model=str(config.get("model", "pyannote/speaker-diarization-community-1")), device=str(config.get("device", "cuda")), token_env=str(config.get("token_env", "HUGGINGFACE_TOKEN")), min_speakers=config.get("min_speakers"), max_speakers=config.get("max_speakers"), use_exclusive=bool(config.get("use_exclusive", True)), segmentation_batch_size=config.get("segmentation_batch_size"), embedding_batch_size=config.get("embedding_batch_size"))
