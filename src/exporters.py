from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.models import PipelineResult


def _format_srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def _format_ass_timestamp(seconds: float) -> str:
    centis = int(round(seconds * 100))
    hours, rem = divmod(centis, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"


def export_json(result: PipelineResult, path: Path) -> None:
    path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def export_compliance_report(issues: Iterable[Any], path: Path) -> None:
    payload = [issue.to_dict() if hasattr(issue, "to_dict") else issue for issue in issues]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def export_srt(result: PipelineResult, path: Path) -> None:
    lines: list[str] = []
    for i, segment in enumerate(result.segments, start=1):
        lines.append(str(i))
        lines.append(f"{_format_srt_timestamp(segment.start)} --> {_format_srt_timestamp(segment.end)}")
        # A correction candidate is evidence, not a visible speaker label. Speaker IDs are
        # rendered only by the SDH layer when required for comprehension.
        lines.append(segment.final_text())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def export_ass(result: PipelineResult, path: Path) -> None:
    header = """[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,20,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    events: list[str] = [header]
    for segment in result.segments:
        start = _format_ass_timestamp(segment.start)
        end = _format_ass_timestamp(segment.end)
        label = segment.speaker_name_candidate or ""
        text = segment.final_text().replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start},{end},Default,{label},0,0,0,,{text}")
    path.write_text("\n".join(events), encoding="utf-8")
