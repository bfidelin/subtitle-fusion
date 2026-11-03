from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from typing import Any, Mapping

DEFAULT_PYTHON = "/home/calmos/miniconda3/envs/senko/bin/python"
DEFAULT_SCRIPT = "/home/calmos/subtitle-fusion/scripts/senko_gpu_diarize.py"


@dataclass(slots=True)
class SenkoGpuConfig:
    python: str = DEFAULT_PYTHON
    script: str = DEFAULT_SCRIPT
    timeout_sec: float = 240.0
    _extra: dict[str, Any] | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "SenkoGpuConfig":
        data = data or {}
        allowed = {field for field in cls.__dataclass_fields__ if field != "_extra"}
        return cls(**{k: v for k, v in data.items() if k in allowed})


class SenkoGpuUnavailableError(RuntimeError):
    """Raised when the local Senko diarization subprocess cannot run."""


def run_senko_diarization(media_path: Path, config: SenkoGpuConfig) -> tuple[list[dict[str, Any]], dict[str, list[float]]]:
    media_path = Path(media_path)
    if not media_path.is_file():
        raise FileNotFoundError(f"media file not found: {media_path}")
    if not Path(config.python).is_file():
        raise SenkoGpuUnavailableError("Senko Python environment is not installed")
    if not Path(config.script).is_file():
        raise SenkoGpuUnavailableError("Senko helper script is missing")

    output_dir = Path("/home/calmos/tmp/senko-provider")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"senko_{uuid4().hex}.json"
    command = [config.python, config.script, "--audio", str(media_path), "--output", str(output_path)]
    cp = subprocess.run(command, capture_output=True, text=True, timeout=config.timeout_sec, check=False, cwd="/home/calmos")
    if cp.returncode != 0 or not output_path.is_file():
        raise SenkoGpuUnavailableError(f"Senko failed: {(cp.stderr or cp.stdout)[-500:]}")
    try:
        payload = json.loads(output_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SenkoGpuUnavailableError(f"Senko returned invalid JSON: {exc}") from exc
    return payload.get("speaker_turns", []), payload.get("speaker_embeddings", {})


def assign_speakers(segments: list[Any], turns: list[dict[str, Any]], fallback: str = "UNKNOWN") -> list[dict[str, Any]]:
    ordered = sorted(turns, key=lambda item: (float(item.get("start", 0.0)), float(item.get("end", 0.0))))
    for segment in segments:
        best_speaker = fallback
        best_overlap = 0.0
        for turn in ordered:
            overlap = min(float(segment.end), float(turn.get("end", 0.0))) - max(float(segment.start), float(turn.get("start", 0.0)))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = str(turn.get("speaker", fallback))
        segment.speaker_id = best_speaker
    return turns