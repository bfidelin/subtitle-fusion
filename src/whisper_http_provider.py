from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from src.models import Segment, SpeakerTurn, Word


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _speaker_id(raw: Any) -> str:
    if isinstance(raw, bool):
        return "UNKNOWN"
    if isinstance(raw, int):
        return f"Speaker_{raw + 1}"
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "UNKNOWN"


def normalize_http_segments(raw_segments: Any) -> list[Segment]:
    """Normalize the JSON response returned by the local Whisper ASR API."""
    segments: list[Segment] = []
    if not isinstance(raw_segments, list):
        return _merge_adjacent_same_speaker(segments)

    for index, raw in enumerate(raw_segments, start=1):
        if not isinstance(raw, Mapping):
            continue
        start = _as_float(raw.get("start", 0.0))
        end = _as_float(raw.get("end", start if start is not None else 0.0))
        if start is None:
            start = 0.0
        if end is None:
            end = start

        speaker_id = _speaker_id(raw.get("speaker"))
        text_raw = _as_text(raw.get("text"))
        words: list[Word] = []
        for index, raw_word in enumerate(raw.get("words", []) or []):
            if not isinstance(raw_word, Mapping):
                continue
            word_start = _as_float(raw_word.get("start"))
            word_end = _as_float(raw_word.get("end"))
            if word_start is None or word_end is None:
                continue
            word_speaker = raw_word.get("speaker")
            if word_speaker is None:
                word_speaker = raw.get("speaker")
            confidence = _as_float(
                raw_word.get("confidence", raw_word.get("score", raw_word.get("probability")))
            )
            flags: list[str] = []
            word_text = _as_text(raw_word.get("text", raw_word.get("word")))
            # Context review helper: capitalised tokens (other than first word of a cue)
            # are often proper-noun risk candidate. ASR text is chanted lower-case in
            # subsequent positions, so this stays conservative but useful for review.
            if (
                index > 0
                and len(word_text) >= 3
                and word_text[:1].isupper()
                and word_text[1:].islower()
            ):
                flags.append("proper_noun_candidate")
            words.append(
                Word(
                    text=word_text,
                    start=word_start,
                    end=word_end,
                    confidence=confidence,
                    flags=flags,
                    speaker_id=_speaker_id(word_speaker)
                    if word_speaker is not None
                    else speaker_id,
                )
            )

        if words and not text_raw:
            text_raw = " ".join(word.text for word in words).strip()

        segments.append(
            Segment(
                id=index,
                start=start,
                end=end,
                speaker_id=speaker_id,
                text_raw=text_raw,
                words=words,
            )
        )
    return _coalesce_http_segments(segments)


@dataclass(slots=True)
class WhisperHttpConfig:
    url: str = "http://127.0.0.1:9000/asr"
    language: str | None = None
    engine: str = "faster_whisper"
    model: str | None = None
    encode: bool = True
    task: str = "transcribe"
    vad_filter: bool = True
    word_timestamps: bool = True
    output: str = "json"
    diarize: bool = False
    diarize_threshold: float | None = None
    timeout_sec: float = 720.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "WhisperHttpConfig":
        data = data or {}
        allowed = set(cls.__dataclass_fields__)
        values = {key: value for key, value in data.items() if key in allowed}
        return cls(**values)


class WhisperHttpUnavailableError(RuntimeError):
    """Raised when the local Whisper HTTP endpoint cannot be used."""


class WhisperHttpProvider:
    def __init__(self, config: WhisperHttpConfig):
        self.config = config

    @staticmethod
    def _normalize_endpoint(url: str) -> str:
        url = url.strip()
        if not url:
            raise ValueError("Whisper HTTP URL is empty")
        if not url.endswith("/asr"):
            url = url.rstrip("/") + "/asr"
        return url

    def _build_query(self) -> str:
        params: dict[str, str] = {
            "encode": "true" if self.config.encode else "false",
            "task": self.config.task,
            "vad_filter": "true" if self.config.vad_filter else "false",
            "word_timestamps": "true" if self.config.word_timestamps else "false",
            "output": self.config.output,
            "engine": self.config.engine,
            "diarize": "true" if self.config.diarize else "false",
        }
        if self.config.language:
            params["language"] = self.config.language
        if self.config.model:
            params["model"] = self.config.model
        if self.config.diarize_threshold is not None:
            params["diarize_threshold"] = str(self.config.diarize_threshold)
        return urllib.parse.urlencode(params)

    def _multipart_body(self, media_path: Path) -> tuple[bytes, str]:
        boundary = f"----SubtitleFusionWhisperHttp{uuid4().hex}"
        content_type = mimetypes.guess_type(str(media_path))[0] or "application/octet-stream"
        with media_path.open("rb") as handle:
            file_bytes = handle.read()

        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="audio_file"; '
            f'filename="{media_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("ascii")
        footer = f"\r\n--{boundary}--\r\n".encode("ascii")
        body = header + file_bytes + footer
        return body, f"multipart/form-data; boundary={boundary}"

    def transcribe(self, media_path: Path) -> "WhisperHttpResult":
        media_path = Path(media_path)
        if not media_path.is_file():
            raise FileNotFoundError(f"media file not found: {media_path}")

        endpoint = self._normalize_endpoint(self.config.url)
        query = self._build_query()
        full_url = f"{endpoint}?{query}"
        body, content_type = self._multipart_body(media_path)

        request = urllib.request.Request(
            full_url,
            data=body,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(len(body)),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_sec) as response:
                raw_body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise WhisperHttpUnavailableError(
                f"Whisper HTTP ASR failed with HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise WhisperHttpUnavailableError(f"Whisper HTTP ASR unavailable: {exc}") from exc
        except TimeoutError as exc:
            raise WhisperHttpUnavailableError(
                f"Whisper HTTP ASR timed out after {self.config.timeout_sec}s"
            ) from exc

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WhisperHttpUnavailableError("Whisper HTTP ASR returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise WhisperHttpUnavailableError("Whisper HTTP ASR returned a non-object response")

        segments = normalize_http_segments(payload.get("segments", payload.get("aligned_segments")))
        language = payload.get("language") or payload.get("detected_language")
        if not isinstance(language, str) or not language:
            language = self.config.language

        raw_embeddings = payload.get("speaker_embeddings")
        speaker_embeddings: dict[str, list[float]] = {}
        if isinstance(raw_embeddings, Mapping):
            for speaker_id, vector in raw_embeddings.items():
                if not isinstance(vector, (list, tuple)):
                    continue
                try:
                    speaker_embeddings[str(speaker_id)] = [float(value) for value in vector]
                except (TypeError, ValueError):
                    continue

        return WhisperHttpResult(
            segments=segments,
            speaker_turns=[],
            speaker_embeddings=speaker_embeddings,
            language=language,
        )


@dataclass(slots=True)
class WhisperHttpResult:
    segments: list[Segment]
    speaker_turns: list["SpeakerTurn"]
    speaker_embeddings: dict[str, list[float]]
    language: str | None = None


def _coalesce_http_segments(segments: list[Segment]) -> list[Segment]:
    # Merge only tiny neighbouring cues into a single readable 42-char cue.
    # This is conservative: no punctuation over 42 characters are swallowed.
    merged: list[Segment] = []
    for segment in segments:
        if not merged:
            merged.append(segment)
            continue
        previous = merged[-1]
        total = len(previous.text_raw) + 1 + len(segment.text_raw)
        if (
            (len(previous.words) <= 3 or previous.end - previous.start < 0.6)
            and total <= 42
            and float(segment.start) - float(previous.end) <= 0.5
            and len(previous.words) + len(segment.words) <= 6
        ):
            previous.end = max(float(previous.end), float(segment.end))
            previous.text_raw = f"{previous.text_raw} {segment.text_raw}".strip()
            previous.words.extend(segment.words)
            previous.speaker_id = (
                previous.speaker_id
                if previous.speaker_id == segment.speaker_id
                else previous.speaker_id
            )
        else:
            merged.append(segment)
    for index, segment in enumerate(merged, start=1):
        segment.id = index
    return merged


def _merge_adjacent_same_speaker(segments: list[Segment]) -> list[Segment]:
    merged: list[Segment] = []
    for segment in segments:
        if not merged:
            merged.append(segment)
            continue
        previous = merged[-1]
        gap = float(segment.start) - float(previous.end)
        combined = len(previous.text_raw) + 1 + len(segment.text_raw)
        previous_short = len(previous.words) <= 4 and len(previous.text_raw) <= 20

        # Only join truly tiny fragments from the same speaker. This avoids merging
 # an unrelated sentence boundary.
        if previous.speaker_id == segment.speaker_id and gap <= 0.5 and previous_short and combined <= 84 and len(segment.words) <= 10:
            previous.end = max(float(previous.end), float(segment.end))
            previous.text_raw = f"{previous.text_raw} {segment.text_raw}".strip()
            previous.words.extend(segment.words)
        else:
            merged.append(segment)
    for index, segment in enumerate(merged, start=1):
        segment.id = index
    return merged
