from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.models import Segment


TEXT_SUBTITLE_CODECS = {
    "ass",
    "mov_text",
    "srt",
    "ssa",
    "subrip",
    "text",
    "ttml",
    "webvtt",
}


class EmbeddedSubtitleUnavailableError(RuntimeError):
    """Raised when the media has no usable text subtitle stream."""


@dataclass(slots=True)
class EmbeddedSubtitleConfig:
    language: str | None = None
    stream_index: int | None = None
    timeout_sec: float = 120.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "EmbeddedSubtitleConfig":
        data = data or {}
        allowed = {field for field in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in allowed})


class EmbeddedSubtitleProvider:
    def __init__(self, config: EmbeddedSubtitleConfig):
        self.config = config

    @staticmethod
    def _probe_streams(media_path: Path) -> list[dict[str, Any]]:
        cp = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "s",
                "-show_entries",
                "stream=index,codec_name:stream_tags=language,title",
                "-of",
                "json",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        payload = json.loads(cp.stdout or "{}")
        return [stream for stream in payload.get("streams", []) if isinstance(stream, dict)]

    def _select_stream(self, streams: list[dict[str, Any]]) -> dict[str, Any]:
        if self.config.stream_index is not None:
            for stream in streams:
                if int(stream.get("index", -1)) == int(self.config.stream_index):
                    return stream
            raise EmbeddedSubtitleUnavailableError(
                f"embedded subtitle stream {self.config.stream_index} not found"
            )

        text_streams = [
            stream
            for stream in streams
            if str(stream.get("codec_name", "")).lower() in TEXT_SUBTITLE_CODECS
        ]
        if not text_streams:
            raise EmbeddedSubtitleUnavailableError("no text subtitle stream")

        if self.config.language:
            wanted = str(self.config.language).lower()
            for stream in text_streams:
                lang = str(stream.get("tags", {}).get("language", "")).lower()
                if lang and lang.startswith(wanted[:2]):
                    return stream
        return text_streams[0]

    @staticmethod
    def _ts_to_seconds(value: str) -> float:
        match = re.match(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})", value.strip())
        if not match:
            return 0.0
        h, m, s, ms = match.groups()
        ms = (ms + "000")[:3]
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    @staticmethod
    def _parse_srt(text: str) -> list[Segment]:
        segments: list[Segment] = []
        for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            if lines[0].isdigit():
                lines = lines[1:]
            cue_match = re.match(
                r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})",
                lines[0] if lines else "",
            )
            if not cue_match:
                continue
            start = EmbeddedSubtitleProvider._ts_to_seconds(cue_match.group(1))
            end = EmbeddedSubtitleProvider._ts_to_seconds(cue_match.group(2))
            text_lines = lines[1:]
            if not text_lines:
                continue
            cleaned = " ".join(text_lines).strip()
            cleaned = re.sub(r"<[^>]*>", "", cleaned)
            if not cleaned:
                continue
            segments.append(
                Segment(
                    id=len(segments) + 1,
                    start=start,
                    end=max(end, start),
                    speaker_id="UNKNOWN",
                    text_raw=cleaned,
                    words=[],
                )
            )
        return segments

    def transcribe(self, media_path: Path) -> "EmbeddedSubtitleResult":
        media_path = Path(media_path)
        if not media_path.is_file():
            raise FileNotFoundError(f"media file not found: {media_path}")

        streams = self._probe_streams(media_path)
        stream = self._select_stream(streams)

        with tempfile.TemporaryDirectory(prefix="subtitle-fusion-embedded-") as tmp:
            srt_path = Path(tmp) / "embedded.srt"
            cp = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-nostdin",
                    "-i",
                    str(media_path),
                    "-map",
                    f"0:{int(stream['index'])}",
                    "-c:s",
                    "srt",
                    str(srt_path),
                ],
                capture_output=True,
                text=True,
                timeout=self.config.timeout_sec,
                check=False,
            )
            if cp.returncode != 0 or not srt_path.is_file() or srt_path.stat().st_size == 0:
                raise EmbeddedSubtitleUnavailableError(
                    f"failed to extract embedded subtitle stream: {cp.stderr[-500:]}"
                )
            srt_text = srt_path.read_text(encoding="utf-8", errors="replace")

        segments = self._parse_srt(srt_text)
        if not segments:
            raise EmbeddedSubtitleUnavailableError("embedded subtitle produced no cues")

        language = str(stream.get("tags", {}).get("language") or "").strip() or self.config.language
        if not language:
            language = None

        from src.models import SpeakerTurn

        return EmbeddedSubtitleResult(
            segments=segments,
            speaker_turns=[],
            speaker_embeddings={},
            language=language,
        )


@dataclass(slots=True)
class EmbeddedSubtitleResult:
    segments: list[Segment]
    speaker_turns: list["SpeakerTurn"]
    speaker_embeddings: dict[str, list[float]]
    language: str | None = None
