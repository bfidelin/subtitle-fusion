from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.models import Segment, Word


DEFAULT_SCORING_PATH = Path("config/scoring.yaml")


class ScoringConfig(dict):
    @property
    def weights(self) -> dict[str, float]:
        return self.get("weights", {})

    @property
    def thresholds(self) -> dict[str, float]:
        return self.get("thresholds", {})

    @property
    def low_confidence(self) -> dict[str, float]:
        return self.get("low_confidence", {})


def load_scoring_config(path: Path = DEFAULT_SCORING_PATH) -> ScoringConfig:
    with path.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle) or {}
    return ScoringConfig(data)


def segment_average_confidence(segment: Segment) -> float | None:
    values = [w.confidence for w in segment.words if w.confidence is not None]
    if not values:
        return None
    return sum(values) / len(values)


def has_low_confidence_word(segment: Segment, threshold: float) -> bool:
    return any(w.confidence is not None and w.confidence < threshold for w in segment.words)


def word_needs_review(word: Word, threshold: float) -> bool:
    if word.confidence is not None and word.confidence < threshold:
        return True
    return "proper_noun_candidate" in word.flags or "context_review" in word.flags


def annotate_uncertain_words(segment: Segment, cfg: ScoringConfig) -> Segment:
    threshold = cfg.low_confidence.get("word", 0.65)
    for word in segment.words:
        if word.confidence is not None and word.confidence < threshold:
            if "low_confidence" not in word.flags:
                word.flags.append("low_confidence")
            if "context_review" not in word.flags:
                word.flags.append("context_review")
        if "proper_noun_candidate" in word.flags and "context_review" not in word.flags:
            word.flags.append("context_review")
    return segment


def uncertain_words(segment: Segment, cfg: ScoringConfig) -> list[Word]:
    threshold = cfg.low_confidence.get("word", 0.65)
    return [word for word in segment.words if word_needs_review(word, threshold)]


def segment_needs_review(segment: Segment, cfg: ScoringConfig) -> bool:
    annotate_uncertain_words(segment, cfg)
    word_threshold = cfg.low_confidence.get("word", 0.65)
    segment_threshold = cfg.low_confidence.get("segment_avg", 0.75)
    avg = segment_average_confidence(segment)
    has_proper_noun_risk = any("proper_noun_candidate" in w.flags for w in segment.words)
    has_context_review_words = any(word_needs_review(w, word_threshold) for w in segment.words)
    return (
        has_low_confidence_word(segment, word_threshold)
        or (avg is not None and avg < segment_threshold)
        or has_proper_noun_risk
        or has_context_review_words
    )


def lexical_similarity(a: str, b: str) -> float:
    a_set = set(a.lower().split())
    b_set = set(b.lower().split())
    if not a_set or not b_set:
        return 0.0
    inter = len(a_set & b_set)
    union = len(a_set | b_set)
    return inter / union
