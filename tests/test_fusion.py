from src.fusion import resolve_segment
from src.models import Candidate, OCRHit, Segment, Word
from src.scoring import ScoringConfig


def test_resolve_segment_suggest_or_correct() -> None:
    cfg = ScoringConfig(
        {
            "weights": {
                "asr_low_confidence": 1.5,
                "ocr_exact_match": 4.0,
                "imdb_character_match": 3.0,
                "lexical_similarity": 1.5,
            },
            "thresholds": {"auto_correct": 6.0, "suggest_only": 3.5},
            "low_confidence": {"word": 0.65},
        }
    )
    segment = Segment(
        id=1,
        start=0.0,
        end=1.0,
        speaker_id="S1",
        text_raw="Murel, on verrouille tout.",
        words=[Word(text="Murel", start=0.0, end=0.2, confidence=0.4)],
        ocr_hits=[OCRHit(text="Morel", time=0.1, confidence=0.9)],
        imdb_candidates=[Candidate(type="character", name="Morel", score=0.0)],
    )
    decision = resolve_segment(segment, cfg)
    assert decision.status in {"auto_corrected", "suggest_only"}
    assert decision.fusion_score >= 3.5


def test_resolve_segment_without_candidates_keeps_original() -> None:
    cfg = ScoringConfig({"weights": {}, "thresholds": {}, "low_confidence": {"word": 0.65}})
    segment = Segment(
        id=1,
        start=0.0,
        end=1.0,
        speaker_id="S1",
        text_raw="Hello",
        words=[Word(text="Hello", start=0.0, end=0.2, confidence=0.9)],
    )
    decision = resolve_segment(segment, cfg)
    assert decision.status == "kept_original"
