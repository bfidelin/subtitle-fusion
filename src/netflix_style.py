from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from src.models import Segment


_TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]+\}")
_PUNCTUATION_END = (".", ",", ";", ":", "!", "?", "…")
_FRENCH_BREAK_BEFORE = {
    "à",
    "au",
    "aux",
    "avec",
    "car",
    "chez",
    "comme",
    "dans",
    "de",
    "des",
    "donc",
    "du",
    "et",
    "mais",
    "ou",
    "par",
    "parce",
    "pour",
    "quand",
    "que",
    "qui",
    "sans",
    "si",
    "sous",
    "sur",
    "vers",
}
_FRENCH_ARTICLES = {
    "un",
    "une",
    "des",
    "le",
    "la",
    "les",
    "l'",
    "du",
    "de",
    "d'",
    "ce",
    "cet",
    "cette",
    "ces",
    "mon",
    "ma",
    "mes",
    "ton",
    "ta",
    "tes",
    "son",
    "sa",
    "ses",
}


@dataclass(slots=True, frozen=True)
class NetflixStyle:
    locale: str = "fr-FR"
    profile: str = "sdh"
    max_chars_per_line: int = 42
    max_lines: int = 2
    min_duration_sec: float = 5 / 6
    max_duration_sec: float = 7.0
    target_cps: float = 17.0
    max_cps: float = 20.0
    fps: float = 24.0
    min_gap_frames: int = 2
    close_short_gaps_under_sec: float = 0.5

    @property
    def min_gap_sec(self) -> float:
        return self.min_gap_frames / self.fps

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "NetflixStyle":
        data = data or {}
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        values = {key: value for key, value in data.items() if key in allowed}
        return cls(**values)


@dataclass(slots=True, frozen=True)
class ComplianceIssue:
    code: str
    segment_id: int | None
    severity: str
    message: str
    value: float | int | str | None = None
    limit: float | int | str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def visible_text(text: str) -> str:
    return _TAG_RE.sub("", text).replace("\n", " ").strip()


def characters_per_second(text: str, duration: float) -> float:
    if duration <= 0:
        return float("inf")
    return len(visible_text(text)) / duration


def _clean_token(token: str) -> str:
    return token.strip("\"'«»()[]{}.,;:!?…").lower()


def _looks_like_name_boundary(left: str, right: str) -> bool:
    left_clean = left.strip("\"'«»()[]{}.,;:!?…")
    right_clean = right.strip("\"'«»()[]{}.,;:!?…")
    return bool(left_clean and right_clean and left_clean[0].isupper() and right_clean[0].isupper())


def _split_score(tokens: list[str], index: int) -> float:
    left_tokens = tokens[:index]
    right_tokens = tokens[index:]
    left = " ".join(left_tokens)
    right = " ".join(right_tokens)

    # Netflix favours readable syntactic breaks and, when equivalent, a bottom-heavy shape.
    score = abs(len(left) - len(right))
    if len(left) > len(right):
        score += (len(left) - len(right)) * 1.5
    if len(left_tokens) <= 2:
        score += 12
    if left.endswith(_PUNCTUATION_END):
        score -= 8
    if _clean_token(right_tokens[0]) in _FRENCH_BREAK_BEFORE:
        score -= 5
    if _clean_token(left_tokens[-1]) in _FRENCH_ARTICLES:
        score += 20
    if _looks_like_name_boundary(left_tokens[-1], right_tokens[0]):
        score += 15
    return score


def format_netflix_text(text: str, style: NetflixStyle) -> str:
    existing = [line.strip() for line in text.splitlines() if line.strip()]
    if existing and len(existing) <= style.max_lines and all(
        len(visible_text(line)) <= style.max_chars_per_line for line in existing
    ):
        return "\n".join(existing)

    flat = " ".join(text.split())
    if len(visible_text(flat)) <= style.max_chars_per_line:
        return flat

    tokens = flat.split()
    candidates: list[tuple[float, str, str]] = []
    for index in range(1, len(tokens)):
        left = " ".join(tokens[:index])
        right = " ".join(tokens[index:])
        if (
            len(visible_text(left)) <= style.max_chars_per_line
            and len(visible_text(right)) <= style.max_chars_per_line
        ):
            candidates.append((_split_score(tokens, index), left, right))

    if not candidates:
        # Never truncate or paraphrase silently. The validator will mark it for review.
        return flat

    _, left, right = min(candidates, key=lambda item: item[0])
    return f"{left}\n{right}"


def apply_timing_style(segments: list[Segment], style: NetflixStyle) -> None:
    ordered = sorted(segments, key=lambda segment: (segment.start, segment.end, segment.id))
    for index, segment in enumerate(ordered):
        next_segment = ordered[index + 1] if index + 1 < len(ordered) else None
        duration = segment.end - segment.start

        if duration < style.min_duration_sec:
            desired_end = segment.start + style.min_duration_sec
            if next_segment is None or desired_end <= next_segment.start - style.min_gap_sec:
                segment.end = desired_end

        if next_segment is None:
            continue

        gap = next_segment.start - segment.end
        if style.min_gap_sec < gap < style.close_short_gaps_under_sec:
            desired_end = next_segment.start - style.min_gap_sec
            if desired_end - segment.start <= style.max_duration_sec:
                segment.end = desired_end


def apply_netflix_style(segments: list[Segment], style: NetflixStyle) -> None:
    for segment in segments:
        formatted = format_netflix_text(segment.final_text(), style)
        if formatted != segment.final_text():
            segment.text_corrected = formatted
    apply_timing_style(segments, style)


def validate_segment(segment: Segment, style: NetflixStyle) -> list[ComplianceIssue]:
    issues: list[ComplianceIssue] = []
    text = segment.final_text()
    lines = text.splitlines() or [text]
    duration = segment.end - segment.start

    if duration < style.min_duration_sec:
        issues.append(
            ComplianceIssue(
                code="duration_too_short",
                segment_id=segment.id,
                severity="error",
                message="Subtitle duration is below the Netflix minimum.",
                value=round(duration, 3),
                limit=round(style.min_duration_sec, 3),
            )
        )
    if duration > style.max_duration_sec:
        issues.append(
            ComplianceIssue(
                code="duration_too_long",
                segment_id=segment.id,
                severity="error",
                message="Subtitle duration exceeds the Netflix maximum.",
                value=round(duration, 3),
                limit=style.max_duration_sec,
            )
        )
    if len(lines) > style.max_lines:
        issues.append(
            ComplianceIssue(
                code="too_many_lines",
                segment_id=segment.id,
                severity="error",
                message="Subtitle has more than two lines.",
                value=len(lines),
                limit=style.max_lines,
            )
        )
    for line_number, line in enumerate(lines, start=1):
        line_length = len(visible_text(line))
        if line_length > style.max_chars_per_line:
            issues.append(
                ComplianceIssue(
                    code="line_too_long",
                    segment_id=segment.id,
                    severity="error",
                    message=f"Line {line_number} exceeds the character limit.",
                    value=line_length,
                    limit=style.max_chars_per_line,
                )
            )

    cps = characters_per_second(text, duration)
    if cps > style.max_cps:
        issues.append(
            ComplianceIssue(
                code="reading_speed_too_high",
                segment_id=segment.id,
                severity="error",
                message="Reading speed exceeds the configured Netflix SDH ceiling.",
                value=round(cps, 2),
                limit=style.max_cps,
            )
        )
    elif cps > style.target_cps:
        issues.append(
            ComplianceIssue(
                code="reading_speed_above_target",
                segment_id=segment.id,
                severity="warning",
                message="Reading speed is above the preferred subtitle target.",
                value=round(cps, 2),
                limit=style.target_cps,
            )
        )
    return issues


def validate_result(segments: list[Segment], style: NetflixStyle) -> list[ComplianceIssue]:
    issues = [issue for segment in segments for issue in validate_segment(segment, style)]
    ordered = sorted(segments, key=lambda segment: (segment.start, segment.end, segment.id))
    for previous, current in zip(ordered, ordered[1:]):
        gap = current.start - previous.end
        if 0 <= gap < style.min_gap_sec:
            issues.append(
                ComplianceIssue(
                    code="gap_too_short",
                    segment_id=current.id,
                    severity="error",
                    message="Gap from previous subtitle is below two frames.",
                    value=round(gap, 4),
                    limit=round(style.min_gap_sec, 4),
                )
            )
        elif style.min_gap_sec < gap < style.close_short_gaps_under_sec:
            issues.append(
                ComplianceIssue(
                    code="short_gap_not_chained",
                    segment_id=current.id,
                    severity="warning",
                    message="Short gap should normally be chained to a two-frame gap.",
                    value=round(gap, 4),
                    limit=style.close_short_gaps_under_sec,
                )
            )
    return issues
