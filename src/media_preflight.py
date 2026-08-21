from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TEXT_SUBTITLE_CODECS = {
    "subrip",
    "srt",
    "ass",
    "ssa",
    "webvtt",
    "mov_text",
    "text",
    "ttml",
}
IMAGE_SUBTITLE_CODECS = {
    "hdmv_pgs_subtitle",
    "dvd_subtitle",
    "dvb_subtitle",
    "xsub",
}


class MediaPreflightError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str | None = None
    language: str | None = None
    title: str | None = None
    default: bool = False
    forced: bool = False

    @property
    def is_text_subtitle(self) -> bool:
        return self.codec_type == "subtitle" and (self.codec_name or "") in TEXT_SUBTITLE_CODECS

    @property
    def is_image_subtitle(self) -> bool:
        return self.codec_type == "subtitle" and (self.codec_name or "") in IMAGE_SUBTITLE_CODECS


@dataclass(slots=True)
class MediaInventory:
    duration_sec: float | None = None
    format_name: str | None = None
    streams: list[StreamInfo] = field(default_factory=list)

    @property
    def audio_streams(self) -> list[StreamInfo]:
        return [stream for stream in self.streams if stream.codec_type == "audio"]

    @property
    def subtitle_streams(self) -> list[StreamInfo]:
        return [stream for stream in self.streams if stream.codec_type == "subtitle"]

    @property
    def text_subtitle_streams(self) -> list[StreamInfo]:
        return [stream for stream in self.subtitle_streams if stream.is_text_subtitle]

    @property
    def image_subtitle_streams(self) -> list[StreamInfo]:
        return [stream for stream in self.subtitle_streams if stream.is_image_subtitle]

    def preferred_text_subtitle(self, language: str | None = None) -> StreamInfo | None:
        candidates = self.text_subtitle_streams
        if language:
            normalized = language.lower()
            language_matches = [
                stream
                for stream in candidates
                if (stream.language or "").lower() == normalized
                or (stream.language or "").lower().startswith(normalized)
            ]
            if language_matches:
                candidates = language_matches
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (not item.default, not item.forced, item.index))[0]


def _bool_disposition(value: Any) -> bool:
    return bool(value in {1, True, "1", "true", "True"})


def parse_ffprobe(payload: dict[str, Any]) -> MediaInventory:
    format_data = payload.get("format") or {}
    raw_duration = format_data.get("duration")
    try:
        duration = float(raw_duration) if raw_duration is not None else None
    except (TypeError, ValueError):
        duration = None

    streams: list[StreamInfo] = []
    for raw in payload.get("streams") or []:
        tags = raw.get("tags") or {}
        disposition = raw.get("disposition") or {}
        streams.append(
            StreamInfo(
                index=int(raw.get("index", len(streams))),
                codec_type=str(raw.get("codec_type", "unknown")),
                codec_name=raw.get("codec_name"),
                language=tags.get("language"),
                title=tags.get("title"),
                default=_bool_disposition(disposition.get("default")),
                forced=_bool_disposition(disposition.get("forced")),
            )
        )

    return MediaInventory(
        duration_sec=duration,
        format_name=format_data.get("format_name"),
        streams=streams,
    )


def probe_media(path: Path, *, ffprobe: str = "ffprobe") -> MediaInventory:
    executable = shutil.which(ffprobe)
    if not executable:
        raise MediaPreflightError(f"ffprobe not found: {ffprobe}")
    command = [
        executable,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or str(exc)
        raise MediaPreflightError(f"ffprobe failed: {message}") from exc
    return parse_ffprobe(json.loads(completed.stdout))
