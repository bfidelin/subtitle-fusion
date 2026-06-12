from src.models import Segment, Word
from src.scoring import ScoringConfig, annotate_uncertain_words, uncertain_words


def test_annotate_uncertain_words_marks_low_confidence_and_context_review() -> None:
    cfg = ScoringConfig({"low_confidence": {"word": 0.65}})
    segment = Segment(
        id=1,
        start=0.0,
        end=1.0,
        speaker_id="S1",
        text_raw="Murel arrives",
        words=[
            Word(text="Murel", start=0.0, end=0.2, confidence=0.4, flags=["proper_noun_candidate"]),
            Word(text="arrives", start=0.2, end=0.5, confidence=0.95),
        ],
    )

    annotate_uncertain_words(segment, cfg)

    assert "low_confidence" in segment.words[0].flags
    assert "context_review" in segment.words[0].flags
    assert "proper_noun_candidate" in segment.words[0].flags


def test_uncertain_words_returns_only_words_needing_review() -> None:
    cfg = ScoringConfig({"low_confidence": {"word": 0.65}})
    segment = Segment(
        id=1,
        start=0.0,
        end=1.0,
        speaker_id="S1",
        text_raw="hello Morel",
        words=[
            Word(text="hello", start=0.0, end=0.2, confidence=0.95),
            Word(text="Morel", start=0.2, end=0.4, confidence=0.9, flags=["proper_noun_candidate"]),
        ],
    )

    annotate_uncertain_words(segment, cfg)
    result = uncertain_words(segment, cfg)

    assert len(result) == 1
    assert result[0].text == "Morel"
    assert "context_review" in result[0].flags
