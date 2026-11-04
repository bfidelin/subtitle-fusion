from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DEFAULT_PYTHON = "/home/calmos/miniconda3/envs/nemo-diar/bin/python"
DEFAULT_SCRIPT = "/home/calmos/subtitle-fusion/scripts/pyannote_gpu_diarize.py"


@dataclass(slots=True)
class PyannoteGpuConfig:
    python: str = DEFAULT_PYTHON
    script: str = DEFAULT_SCRIPT
    min_speakers: int | None = None
    max_speakers: int | None = None
    timeout_sec: float = 240.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "PyannoteGpuConfig":
        data = data or {}
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


class PyannoteGpuUnavailableError(RuntimeError):
    """Raised when the local pyannote subprocess cannot run."""


def run_pyannote_diarization(
    media_path: Path, config: PyannoteGpuConfig
) -> tuple[list[dict[str, Any]], dict[str, list[float]]]:
    media_path = Path(media_path)
    if not media_path.is_file():
        raise FileNotFoundError(f"media file not found: {media_path}")
    if not Path(config.python).is_file():
        raise PyannoteGpuUnavailableError("pyannote Python environment is not installed")
    if not Path(config.script).is_file():
        raise PyannoteGpuUnavailableError("pyannote helper script is missing")

    with tempfile.TemporaryDirectory(prefix="subtitle-fusion-pyannote-") as tmp:
        output_path = Path(tmp) / "pyannote.json"
        command = [
            config.python,
            config.script,
            "--audio",
            str(media_path),
            "--output",
            str(output_path),
        ]
        if config.min_speakers is not None:
            command += ["--min-speakers", str(config.min_speakers)]
        if config.max_speakers is not None:
            command += ["--max-speakers", str(config.max_speakers)]

        env = os.environ.copy()
        for dotenv in ("/home/calmos/.env", "/home/calmos/subtitle-fusion/.env"):
            try:
                for line in Path(dotenv).read_text().splitlines():
                    line = line.strip()
                    if line.startswith("HF_TOKEN=") and "HF_TOKEN" not in env:
                        env["HF_TOKEN"] = line.split("=", 1)[1].strip().strip('"').strip("'")
            except OSError:
                continue

        cp = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=config.timeout_sec,
            check=False,
            env=env,
            cwd="/home/calmos",
        )
        if cp.returncode != 0 or not output_path.is_file():
            raise PyannoteGpuUnavailableError(f"pyannote failed: {(cp.stderr or cp.stdout)[-500:]}")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PyannoteGpuUnavailableError(f"pyannote returned invalid JSON: {exc}") from exc
        turns = [item for item in payload.get("speaker_turns", []) if isinstance(item, dict)]
        embeddings = {
            str(k): [float(x) for x in v]
            for k, v in payload.get("speaker_embeddings", {}).items()
            if isinstance(v, list)
        }
        return turns, embeddings


def assign_speakers(
    segments: list[Any], turns: list[dict[str, Any]], fallback: str = "UNKNOWN"
) -> list[dict[str, Any]]:
    ordered = sorted(
        turns, key=lambda item: (float(item.get("start", 0.0)), float(item.get("end", 0.0)))
    )
    for segment in segments:
        best_speaker = fallback
        best_overlap = 0.0
        for turn in ordered:
            overlap = min(float(segment.end), float(turn.get("end", 0.0))) - max(
                float(segment.start), float(turn.get("start", 0.0))
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = str(turn.get("speaker", fallback))
        segment.speaker_id = best_speaker
    return turns


def segment_by_pyannote_turns(segments, turns):
    ordered = sorted(
        turns, key=lambda item: (float(item.get("start", 0.0)), float(item.get("end", 0.0)))
    )

    def speaker_for(word):
        start = float(word.start)
        end = float(word.end)
        best = "UNKNOWN"
        best_overlap = -1.0
        for turn in ordered:
            turn_start = float(turn.get("start", 0.0))
            turn_end = float(turn.get("end", turn_start))
            overlap = min(end, turn_end) - max(start, turn_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best = str(turn.get("speaker", "UNKNOWN"))
        for turn in ordered:
            boundary = float(turn.get("start", 0.0))
            if start + 0.05 < boundary < end - 0.05:
                return str(turn.get("speaker", "UNKNOWN"))
        if best != "UNKNOWN":
            return best
        best = "UNKNOWN"
        best_distance = float("inf")
        for turn in ordered:
            turn_start = float(turn.get("start", 0.0))
            turn_end = float(turn.get("end", turn_start))
            distance = max(turn_start - end, start - turn_end, 0.0)
            if distance < best_distance:
                best_distance = distance
                best = str(turn.get("speaker", "UNKNOWN"))
        return best

    result = []
    for segment in segments:
        words = getattr(segment, "words", []) or []
        if not words:
            result.append(segment)
            continue
        groups = []
        current = []
        current_speaker = None
        for word in words:
            speaker = speaker_for(word)
            if current and (speaker != current_speaker or word.start - current[-1].end > 0.5):
                groups.append((current, current_speaker or "UNKNOWN"))
                current = []
            current.append(word)
            current_speaker = speaker
        if current:
            groups.append((current, current_speaker or "UNKNOWN"))

        for group, speaker in groups:
            if not group:
                continue
            new_segment = type(segment)(
                id=segment.id,
                start=float(group[0].start),
                end=float(group[-1].end),
                speaker_id=speaker,
                text_raw=" ".join(word.text.strip() for word in group).strip(),
                words=list(group),
                speaker_name_candidate=segment.speaker_name_candidate,
                speaker_identity_confidence=segment.speaker_identity_confidence,
                diarization_confidence=segment.diarization_confidence,
                overlap_speakers=list(segment.overlap_speakers),
                character_candidate=segment.character_candidate,
                actor_candidate=segment.actor_candidate,
                ocr_hits=list(segment.ocr_hits),
                imdb_candidates=list(segment.imdb_candidates),
                vision_candidates=list(segment.vision_candidates),
                events=list(segment.events),
                music=segment.music,
                decision=None,
                text_corrected=None,
            )
            result.append(new_segment)
    for index, segment in enumerate(result, start=1):
        segment.id = index
    return result
