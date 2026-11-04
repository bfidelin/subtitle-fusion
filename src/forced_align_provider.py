from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

DEFAULT_PYTHON = "/home/calmos/miniconda3/envs/senko/bin/python"
DEFAULT_SCRIPT = "/home/calmos/subtitle-fusion/scripts/forced_align_worker.py"


class ForcedAlignmentUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class ForcedAlignConfig:
    python: str = DEFAULT_PYTHON
    script: str = DEFAULT_SCRIPT
    timeout_sec: float = 240.0
    language: str = "en"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "ForcedAlignConfig":
        data = data or {}
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


def align_segments(media_path: Path, segments: list[Any], config: ForcedAlignConfig) -> list[Any]:
    if not Path(config.python).is_file():
        raise ForcedAlignmentUnavailableError(
            "forced-alignment Python environment is not installed"
        )
    if not Path(config.script).is_file():
        raise ForcedAlignmentUnavailableError("forced-alignment worker is missing")
    if config.language not in {"en", "eng", None}:
        return segments
    payload = []
    for segment in segments:
        words = []
        for word in getattr(segment, "words", []) or []:
            words.append(
                {
                    "text": str(getattr(word, "text", "")),
                    "start": float(getattr(word, "start", 0.0)),
                    "end": float(getattr(word, "end", 0.0)),
                    "speaker_id": str(getattr(word, "speaker_id", None) or segment.speaker_id),
                    "confidence": getattr(word, "confidence", None),
                }
            )
        payload.append(
            {
                "id": int(segment.id),
                "start": float(segment.start),
                "end": float(segment.end),
                "words": words,
            }
        )

    work_dir = Path("/home/calmos/tmp/forced-align")
    work_dir.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    input_path = work_dir / f"segments_{token}.json"
    output_path = work_dir / f"aligned_{token}.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    command = [
        config.python,
        config.script,
        "--media",
        str(media_path),
        "--segments",
        str(input_path),
        "--output",
        str(output_path),
        "--language",
        config.language,
    ]
    cp = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=config.timeout_sec,
        check=False,
        cwd="/home/calmos",
    )
    if cp.returncode != 0 or not output_path.is_file():
        raise ForcedAlignmentUnavailableError(
            f"forced alignment failed: {(cp.stderr or cp.stdout)[-500:]}"
        )
    try:
        aligned = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ForcedAlignmentUnavailableError(f"invalid alignment JSON: {exc}") from exc
    by_id = {int(item["id"]): item for item in aligned if item.get("id") is not None}
    for segment in segments:
        record = by_id.get(int(segment.id))
        if not record:
            continue
        words = record.get("words") or []
        if len(words) != len(getattr(segment, "words", []) or []):
            continue
        for word, data in zip(segment.words, words):
            word.start = float(data.get("start", word.start))
            word.end = float(data.get("end", word.end))
            if data.get("speaker_id"):
                word.speaker_id = str(data["speaker_id"])
    return segments
