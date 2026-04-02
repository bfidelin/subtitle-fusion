from src.models import Segment, Word
from src.scoring import ScoringConfig, lexical_similarity, segment_average_confidence, segment_needs_review


def test_segment_average_confidence() -> None:
    segment = Segment(
        id=1,
        start=0.0,
        end=1.0,
        speaker_id="S1",
        text_raw="hello",
        words=[
            Word(text="a", start=0.0, end=0.1, confidence=0.5),
            Word(text="b", start=0.1, end=0.2, confidence=1.0),
        ],
    )
    assert segment_average_confidence(segment) == 0.75


def test_segment_needs_review_on_low_confidence() -> None:
    cfg = ScoringConfig({"low_confidence": {"word": 0.65, "segment_avg": 0.75}})
    segment = Segment(
        id=1,
        start=0.0,
        end=1.0,
        speaker_id="S1",
        text_raw="Murel",
        words=[Word(text="Murel", start=0.0, end=0.3, confidence=0.4)],
    )
    assert segment_needs_review(segment, cfg)


def test_lexical_similarity_overlap() -> None:
    assert lexical_similarity("Commissaire Morel", "Morel") > 0
