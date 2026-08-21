from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def require_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise MediaError("ffmpeg is required but was not found in PATH")
    return executable


def extract_audio(
    video_path: Path,
    output_path: Path,
    *,
    sample_rate: int = 16_000,
    channels: int = 1,
) -> Path:
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    ffmpeg = require_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise MediaError(f"ffmpeg audio extraction failed for {video_path}") from exc
    return output_path
