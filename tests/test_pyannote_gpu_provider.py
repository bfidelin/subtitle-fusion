from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.pyannote_gpu_provider import (
    PyannoteGpuConfig,
    run_pyannote_diarization,
    assign_speakers,
    segment_by_pyannote_turns,
)


def test_config_from_mapping_filters_unknown_keys() -> None:
    config = PyannoteGpuConfig.from_mapping(
        {"python": "/tmp/python", "min_speakers": 2, "unknown": "ignored"}
    )
    assert config.python == "/tmp/python"
    assert config.min_speakers == 2


def test_run_pyannote_diarization_parses_subprocess_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "episode.mkv"
    audio.write_bytes(b"fake media")
    python_path = tmp_path / "python"
    script_path = tmp_path / "script.py"
    python_path.write_text("#!/bin/sh\n", encoding="utf-8")
    script_path.write_text("# fake helper\n", encoding="utf-8")
    output_payload = {
        "speaker_turns": [
            {"start": 0.0, "end": 1.0, "speaker": "Speaker_1"},
            {"start": 1.0, "end": 2.0, "speaker": 1},
        ],
        "speaker_embeddings": {"Speaker_1": [1.0, 2.0], "Speaker_2": [3.0, 4.0]},
    }

    def fake_run(command, **kwargs):
        output_path = Path(command[command.index("--output") + 1])
        output_path.write_text(json.dumps(output_payload), encoding="utf-8")
        return type("Result", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()

    monkeypatch.setattr("src.pyannote_gpu_provider.subprocess.run", fake_run)
    turns, embeddings = run_pyannote_diarization(
        audio, PyannoteGpuConfig(python=str(python_path), script=str(script_path))
    )

    assert len(turns) == 2
    assert embeddings["Speaker_1"] == [1.0, 2.0]
    assert turns[0]["speaker"] == "Speaker_1"
    assert turns[1]["speaker"] == 1


def test_assign_speakers_and_segment_joining() -> None:
    from dataclasses import dataclass, field as dc_field
    from src.models import Word

    @dataclass
    class Segment:
        id: int
        start: float
        end: float
        speaker_id: str
        text_raw: str
        words: list[Word] = dc_field(default_factory=list)

    words = [
        Word(text="Previously", start=0.0, end=0.5),
        Word(text="on", start=0.5, end=0.8),
        Word(text="Hello", start=1.0, end=1.2),
    ]
    segments = [Segment(id=1, start=0.0, end=1.2, speaker_id="UNKNOWN", text_raw="Previously on Hello", words=words)]
    turns = [
        {"start": 0.0, "end": 0.85, "speaker": "Speaker_1"},
        {"start": 0.85, "end": 1.3, "speaker": "Speaker_2"},
    ]

    assign_speakers(segments, turns)
    assert segments[0].speaker_id == "Speaker_1"

# Segment 0: The exact shared helper now lives in src/pyannote_gpu_provider together
# with the actual output; whitespace mirrors mapping turns above.
def test_segment_by_pyannote_turns_basic() -> None:
    from dataclasses import dataclass, field as dc_field
    from src.models import Word

    @dataclass
    class Segment:
        id: int
        start: float
        end: float
        speaker_id: str
        text_raw: str
        words: list[Word] = dc_field(default_factory=list)
        speaker_name_candidate: str | None = None
        speaker_identity_confidence: float | None = None
        diarization_confidence: float | None = None
        overlap_speakers: list[str] = dc_field(default_factory=list)
        character_candidate: str | None = None
        actor_candidate: str | None = None
        ocr_hits: list[Any] = dc_field(default_factory=list)
        imdb_candidates: list[Any] = dc_field(default_factory=list)
        vision_candidates: list[Any] = dc_field(default_factory=list)
        events: list[Any] = dc_field(default_factory=list)
        music: Any = None
        decision: Any = None
        text_corrected: str | None = None

    words = [
        Word(text="Previously", start=0.0, end=0.3),
        Word(text="on", start=0.3, end=0.8),
        Word(text="Hello", start=1.0, end=1.2),
    ]
    segment = Segment(id=1, start=0.0, end=1.2, speaker_id="UNKNOWN", text_raw="Previously on Hello", words=words)
    turns = [
        {"start": 0.0, "end": 0.85, "speaker": "Speaker_1"},
        {"start": 0.85, "end": 1.3, "speaker": "Speaker_2"},
    ]
    result = segment_by_pyannote_turns([segment], turns)
    assert [s.speaker_id for s in result] == ["Speaker_1", "Speaker_2"]
    assert result[0].text_raw == "Previously on"
    assert result[1].text_raw == "Hello"