from __future__ import annotations

import pytest

from src.models import Segment
from src.netflix_style import (
    NetflixStyle,
    apply_netflix_style,
    characters_per_second,
    format_netflix_text,
    validate_result,
)


def make_segment(segment_id: int, start: float, end: float, text: str) -> Segment:
    return Segment(
        id=segment_id,
        start=start,
        end=end,
        speaker_id="speaker",
        text_raw=text,
    )


def test_french_text_is_wrapped_to_two_42_character_lines() -> None:
    style = NetflixStyle()
    text = "Je voulais simplement te dire que nous partirons ensemble demain matin."

    formatted = format_netflix_text(text, style)
    lines = formatted.splitlines()

    assert len(lines) == 2
    assert all(len(line) <= 42 for line in lines)


def test_formatter_never_truncates_text_when_it_cannot_fit() -> None:
    style = NetflixStyle()
    text = "mot " * 30

    formatted = format_netflix_text(text, style)

    assert formatted.replace("\n", " ").split() == text.split()


def test_short_duration_is_extended_when_there_is_room() -> None:
    style = NetflixStyle()
    first = make_segment(1, 0.0, 0.4, "Oui.")
    second = make_segment(2, 2.0, 3.0, "D'accord.")

    apply_netflix_style([first, second], style)

    assert first.end - first.start == pytest.approx(style.min_duration_sec)


def test_short_gap_is_chained_to_two_frames() -> None:
    style = NetflixStyle(fps=24.0)
    first = make_segment(1, 0.0, 1.0, "Première phrase.")
    second = make_segment(2, 1.2, 2.2, "Deuxième phrase.")

    apply_netflix_style([first, second], style)

    assert second.start - first.end == pytest.approx(2 / 24)


def test_high_reading_speed_is_reported() -> None:
    style = NetflixStyle()
    segment = make_segment(1, 0.0, 2.0, "x" * 60)

    issues = validate_result([segment], style)

    assert characters_per_second(segment.final_text(), 2.0) == 30.0
    assert any(issue.code == "reading_speed_too_high" for issue in issues)
    assert any(issue.code == "line_too_long" for issue in issues)
