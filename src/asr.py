from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.models import Segment, Word


class ASRError(RuntimeError):
    pass


@dataclass(slots=True)
class ASRResult:
    segments: list[Segment]
    language: str | None = None
    meta: dict[str, Any] | None = None


class ASRProvider:
    def transcribe(self, audio_path: Path) -> ASRResult:
        raise NotImplementedError


class WhisperXASRProvider(ASRProvider):
    """WhisperX ASR + word alignment with lazy heavy imports."""

    def __init__(self, *, model: str = "large-v3", device: str = "cuda", compute_type: str = "float16", batch_size: int = 16, language: str | None = None) -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.batch_size = batch_size
        self.language = language

    def transcribe(self, audio_path: Path) -> ASRResult:
        try:
            import whisperx
        except ImportError as exc:
            raise ASRError("WhisperX is not installed. Install subtitle-fusion[asr].") from exc

        audio = whisperx.load_audio(str(audio_path))
        model = whisperx.load_model(self.model_name, self.device, compute_type=self.compute_type, language=self.language)
        raw = model.transcribe(audio, batch_size=self.batch_size)
        language = raw.get("language") or self.language
        aligned = raw
        if language:
            align_model, metadata = whisperx.load_align_model(language_code=language, device=self.device)
            aligned = whisperx.align(raw["segments"], align_model, metadata, audio, self.device, return_char_alignments=False)
        return ASRResult(segments=_segments_from_whisperx(aligned.get("segments", [])), language=language, meta={"provider": "whisperx", "model": self.model_name})


class StubASRProvider(ASRProvider):
    def transcribe(self, audio_path: Path) -> ASRResult:
        _ = audio_path
        return ASRResult(segments=[])


def _segments_from_whisperx(raw_segments: list[dict[str, Any]]) -> list[Segment]:
    segments: list[Segment] = []
    for index, raw_segment in enumerate(raw_segments, start=1):
        words: list[Word] = []
        for raw_word in raw_segment.get("words", []) or []:
            start = raw_word.get("start")
            end = raw_word.get("end")
            if start is None or end is None:
                continue
            confidence = raw_word.get("score")
            words.append(Word(text=str(raw_word.get("word", "")).strip(), start=float(start), end=float(end), confidence=float(confidence) if confidence is not None else None))
        start = float(raw_segment.get("start", words[0].start if words else 0.0))
        end = float(raw_segment.get("end", words[-1].end if words else start))
        speaker = str(raw_segment.get("speaker") or "UNKNOWN")
        segments.append(Segment(id=index, start=start, end=end, speaker_id=speaker, text_raw=str(raw_segment.get("text", "")).strip(), words=words))
    return segments


def build_asr_provider(config: dict[str, Any]) -> ASRProvider:
    name = str(config.get("provider", "whisperx")).lower()
    if name == "stub":
        return StubASRProvider()
    if name != "whisperx":
        raise ValueError(f"Unsupported ASR provider: {name}")
    return WhisperXASRProvider(model=str(config.get("model", "large-v3")), device=str(config.get("device", "cuda")), compute_type=str(config.get("compute_type", "float16")), batch_size=int(config.get("batch_size", 16)), language=config.get("language"))
