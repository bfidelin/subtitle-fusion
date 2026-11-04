from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

DEFAULT_PYTHON = "/home/calmos/venvs/speakrs/bin/python"
DEFAULT_SCRIPT = "/home/calmos/subtitle-fusion/scripts/speakrs_diarize.py"


class SpeakrsUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class SpeakrsConfig:
    python: str = DEFAULT_PYTHON
    script: str = DEFAULT_SCRIPT
    mode: str = "cuda"
    profile: str = "precise"
    vocals: bool = False
    timeout_sec: float = 420.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "SpeakrsConfig":
        data = data or {}
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


def run_speakrs_diarization(
    media_path: Path, config: SpeakrsConfig
) -> tuple[list[dict[str, Any]], dict[str, list[float]]]:
    if not Path(config.python).is_file():
        raise SpeakrsUnavailableError("speakrs Python environment is not installed")
    if not Path(config.script).is_file():
        raise SpeakrsUnavailableError("speakrs helper is missing")
    work = Path("/home/calmos/tmp/speakrs-provider")
    work.mkdir(parents=True, exist_ok=True)
    output = work / f"speakrs_{uuid4().hex}.json"
    cp = subprocess.run(
        [
            config.python,
            config.script,
            "--audio",
            str(media_path),
            "--output",
            str(output),
            "--mode",
            config.mode,
            "--profile",
            config.profile,
        ] + (["--vocals"] if config.vocals else []),
        capture_output=True,
        text=True,
        timeout=config.timeout_sec,
        check=False,
        cwd="/home/calmos",
    )
    if cp.returncode != 0 or not output.is_file():
        raise SpeakrsUnavailableError(f"speakrs failed: {(cp.stderr or cp.stdout)[-500:]}")
    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SpeakrsUnavailableError(f"speakrs returned invalid JSON: {exc}") from exc
    return payload.get("speaker_turns", []), payload.get("speaker_embeddings", {})
