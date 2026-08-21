from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models import PipelineResult, Segment


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


def _speaker_prefix(segment: Segment, style: dict[str, Any]) -> str:
    rules = style.get("speaker_labels", {})
    if not rules.get("enabled", True):
        return ""
    name = segment.speaker_name_candidate
    if not name:
        return ""
    if bool(rules.get("show_only_when_needed", True)) and segment.speaker_visible is not False:
        return ""
    return f"{name}: "


def _event_lines(segment: Segment, style: dict[str, Any]) -> list[str]:
    sound_rules = style.get("sounds", {})
    if not sound_rules.get("enabled", True):
        return []
    labels: list[str] = []
    for event in segment.events:
        if event.label.lower() == "music":
            continue
        labels.append(f"[{event.label.lower()}]")
    if segment.music.present:
        mood = f" {segment.music.mood}" if segment.music.mood else ""
        labels.append(f"♪ musique{mood} ♪")
    return labels


def render_sdh_text(segment: Segment, style: dict[str, Any] | None = None) -> str:
    style = style or {}
    lines = _event_lines(segment, style)
    dialogue = f"{_speaker_prefix(segment, style)}{segment.final_text()}".strip()
    if dialogue:
        lines.append(dialogue)
    return "\n".join(lines)


def export_srt(result: PipelineResult, path: Path, *, style: dict[str, Any] | None = None) -> None:
    lines: list[str] = []
    for i, segment in enumerate(result.segments, start=1):
        lines.append(str(i))
        lines.append(f"{_format_srt_timestamp(segment.start)} --> {_format_srt_timestamp(segment.end)}")
        lines.append(render_sdh_text(segment, style))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def export_ass(result: PipelineResult, path: Path, *, style: dict[str, Any] | None = None) -> None:
    header = """[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,44,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,60,60,42,1\nStyle: SDH,Arial,42,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,-1,0,0,100,100,0,0,1,2,1,2,60,60,42,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    events: list[str] = [header]
    for segment in result.segments:
        text = render_sdh_text(segment, style).replace("\n", r"\N")
        ass_style = "SDH" if segment.events or segment.music.present else "Default"
        events.append(f"Dialogue: 0,{_format_ass_timestamp(segment.start)},{_format_ass_timestamp(segment.end)},{ass_style},,0,0,0,,{text}")
    path.write_text("\n".join(events), encoding="utf-8")
