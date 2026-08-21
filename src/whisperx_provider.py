from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.models import Segment, SpeakerTurn, Word


class WhisperXUnavailableError(RuntimeError):
    """Raised when the optional WhisperX runtime is requested but unavailable."""


@dataclass(slots=True, frozen=True)
class WhisperXConfig:
    model: str = "large-v3-turbo"
    device: str = "auto"
    compute_type: str = "float16"
    batch_size: int = 16
    language: str | None = None
    vad_method: str = "pyannote"
    align: bool = True
    diarize: bool = True
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    hf_token_env: str = "HF_TOKEN"
    min_speakers: int | None = None
    max_speakers: int | None = None
    return_embeddings: bool = True
    cache_dir: str | None = None
    fill_nearest_speaker: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "WhisperXConfig":
        data = data or {}
        allowed = set(cls.__dataclass_fields__)
        values = {key: value for key, value in data.items() if key in allowed}
        return cls(**values)


@dataclass(slots=True)
class WhisperXRunResult:
    segments: list[Segment]
    speaker_turns: list[SpeakerTurn]
    speaker_embeddings: dict[str, list[float]]
    language: str | None = None


def _import_whisperx() -> tuple[Any, Any]:
    try:
        whisperx = importlib.import_module("whisperx")
        diarize_module = importlib.import_module("whisperx.diarize")
    except ImportError as exc:
        raise WhisperXUnavailableError(
            'WhisperX is optional. Install it with `pip install -e ".[whisperx]"`.'
        ) from exc
    return whisperx, diarize_module.DiarizationPipeline


def _resolve_device(configured: str) -> str:
    if configured != "auto":
        return configured

    try:
        torch = importlib.import_module("torch")
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _word_confidence(word: Mapping[str, Any]) -> float | None:
    value = word.get("score")
    if value is None:
        value = word.get("probability")
    if value is None:
        return None
    return float(value)


def normalize_whisperx_segments(raw_segments: Sequence[Mapping[str, Any]]) -> list[Segment]:
    normalized: list[Segment] = []
    for index, raw in enumerate(raw_segments, start=1):
        start = float(raw.get("start", 0.0))
        end = float(raw.get("end", start))
        words: list[Word] = []

        for raw_word in raw.get("words", []) or []:
            if "start" not in raw_word or "end" not in raw_word:
                continue
            flags: list[str] = []
            if raw_word.get("speaker") is None:
                flags.append("speaker_unassigned")
            words.append(
                Word(
                    text=str(raw_word.get("word", "")),
                    start=float(raw_word["start"]),
                    end=float(raw_word["end"]),
                    confidence=_word_confidence(raw_word),
                    flags=flags,
                    speaker_id=raw_word.get("speaker"),
                )
            )

        speaker_id = raw.get("speaker") or "UNKNOWN"
        normalized.append(
            Segment(
                id=index,
                start=start,
                end=end,
                speaker_id=str(speaker_id),
                text_raw=str(raw.get("text", "")).strip(),
                words=words,
                diarization_confidence=None,
            )
        )
    return normalized


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, Mapping):
        return row[key]
    try:
        return row[key]
    except (KeyError, TypeError):
        return getattr(row, key)


def diarization_rows(frame: Any) -> Iterable[Any]:
    """Yield rows from a pandas DataFrame or a plain iterable of row mappings."""
    if frame is None:
        return []
    if hasattr(frame, "iterrows"):
        return (row for _, row in frame.iterrows())
    return frame


def build_speaker_turns(frame: Any) -> list[SpeakerTurn]:
    turns = [
        SpeakerTurn(
            start=float(_row_value(row, "start")),
            end=float(_row_value(row, "end")),
            speaker_id=str(_row_value(row, "speaker")),
        )
        for row in diarization_rows(frame)
    ]
    turns.sort(key=lambda turn: (turn.start, turn.end, turn.speaker_id))

    # Sweep only forward until starts are outside the current turn. Real-world
    # diarization has sparse overlaps, so this stays close to linear rather than
    # comparing every turn with every other turn.
    for index, turn in enumerate(turns):
        cursor = index + 1
        while cursor < len(turns) and turns[cursor].start < turn.end:
            other = turns[cursor]
            if other.end > turn.start and other.speaker_id != turn.speaker_id:
                if other.speaker_id not in turn.overlap_speakers:
                    turn.overlap_speakers.append(other.speaker_id)
                if turn.speaker_id not in other.overlap_speakers:
                    other.overlap_speakers.append(turn.speaker_id)
            cursor += 1

    for turn in turns:
        turn.overlap_speakers.sort()
    return turns


def attach_overlap_evidence(segments: list[Segment], turns: Sequence[SpeakerTurn]) -> None:
    if not segments or not turns:
        return

    ordered_turns = sorted(turns, key=lambda turn: (turn.start, turn.end))
    cursor = 0
    for segment in sorted(segments, key=lambda item: (item.start, item.end, item.id)):
        while cursor < len(ordered_turns) and ordered_turns[cursor].end <= segment.start:
            cursor += 1

        speakers: set[str] = set()
        index = cursor
        while index < len(ordered_turns) and ordered_turns[index].start < segment.end:
            turn = ordered_turns[index]
            if turn.end > segment.start:
                speakers.add(turn.speaker_id)
            index += 1

        if len(speakers) > 1:
            segment.overlap_speakers = sorted(speakers)


class WhisperXProvider:
    def __init__(self, config: WhisperXConfig):
        self.config = config

    def transcribe(self, media_path: Path) -> WhisperXRunResult:
        whisperx, DiarizationPipeline = _import_whisperx()
        device = _resolve_device(self.config.device)
        compute_type = self.config.compute_type
        if device == "cpu" and compute_type == "float16":
            compute_type = "int8"

        audio = whisperx.load_audio(str(media_path))
        model = whisperx.load_model(
            self.config.model,
            device,
            compute_type=compute_type,
            language=self.config.language,
            vad_method=self.config.vad_method,
        )
        result = model.transcribe(audio, batch_size=self.config.batch_size)
        language = result.get("language") or self.config.language

        if self.config.align and language:
            align_model, metadata = whisperx.load_align_model(
                language_code=language,
                device=device,
            )
            result = whisperx.align(
                result["segments"],
                align_model,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )

        speaker_turns: list[SpeakerTurn] = []
        speaker_embeddings: dict[str, list[float]] = {}

        if self.config.diarize:
            token = os.getenv(self.config.hf_token_env)
            if not token:
                raise RuntimeError(
                    f"Diarization requires a Hugging Face token in "
                    f"{self.config.hf_token_env!r} and access to "
                    f"{self.config.diarization_model!r}."
                )

            diarizer = DiarizationPipeline(
                model_name=self.config.diarization_model,
                token=token,
                device=device,
                cache_dir=self.config.cache_dir,
            )
            diarized = diarizer(
                audio,
                min_speakers=self.config.min_speakers,
                max_speakers=self.config.max_speakers,
                return_embeddings=self.config.return_embeddings,
            )
            if self.config.return_embeddings:
                diarize_df, embeddings = diarized
                speaker_embeddings = embeddings or {}
            else:
                diarize_df = diarized

            speaker_turns = build_speaker_turns(diarize_df)
            result = whisperx.assign_word_speakers(
                diarize_df,
                result,
                speaker_embeddings=speaker_embeddings or None,
                fill_nearest=self.config.fill_nearest_speaker,
            )

        segments = normalize_whisperx_segments(result.get("segments", []))
        attach_overlap_evidence(segments, speaker_turns)
        return WhisperXRunResult(
            segments=segments,
            speaker_turns=speaker_turns,
            speaker_embeddings=speaker_embeddings,
            language=language,
        )
