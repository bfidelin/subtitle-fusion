from __future__ import annotations

from src.models import Candidate, Decision, Segment
from src.scoring import ScoringConfig, lexical_similarity


def attach_nearby_ocr(segment: Segment, ocr_hits: list) -> Segment:
    segment.ocr_hits = [hit for hit in ocr_hits if segment.start - 1.0 <= hit.time <= segment.end + 1.0]
    return segment


def replace_uncertain_token(text: str, replacement: str) -> str:
    parts = text.split()
    if not parts:
        return text
    parts[0] = replacement
    return " ".join(parts)


def score_candidate(segment: Segment, candidate: Candidate, cfg: ScoringConfig) -> tuple[float, list[str]]:
    weights = cfg.weights
    score = 0.0
    reasons: list[str] = []

    if any(w.confidence is not None and w.confidence < cfg.low_confidence.get("word", 0.65) for w in segment.words):
        score += weights.get("asr_low_confidence", 0.0)
        reasons.append("ASR low confidence")

    for hit in segment.ocr_hits:
        if hit.text.lower() == candidate.name.lower():
            score += weights.get("ocr_exact_match", 0.0)
            reasons.append("OCR exact match")
            break
        if candidate.name.lower() in hit.text.lower() or lexical_similarity(hit.text, candidate.name) > 0.3:
            score += weights.get("ocr_partial_match", 0.0)
            reasons.append("OCR partial match")
            break

    if candidate.type == "character":
        score += weights.get("imdb_character_match", 0.0)
        reasons.append("IMDb character match")
    elif candidate.type == "actor":
        score += weights.get("imdb_actor_match", 0.0)
        reasons.append("IMDb actor match")

    similarity = lexical_similarity(segment.text_raw, candidate.name)
    if similarity > 0:
        score += weights.get("lexical_similarity", 0.0) * similarity
        reasons.append("Lexical similarity")

    return score, reasons


def resolve_segment(segment: Segment, cfg: ScoringConfig) -> Decision:
    candidates = segment.imdb_candidates + segment.vision_candidates
    if not candidates:
        return Decision(
            status="kept_original",
            final_text=segment.text_raw,
            final_label=None,
            fusion_score=0.0,
            reasons=["no candidates available"],
        )

    scored = [(cand, *score_candidate(segment, cand, cfg)) for cand in candidates]
    best, score, reasons = max(scored, key=lambda item: item[1])

    auto_threshold = cfg.thresholds.get("auto_correct", 6.0)
    suggest_threshold = cfg.thresholds.get("suggest_only", 3.5)

    if score >= auto_threshold:
        return Decision(
            status="auto_corrected",
            final_text=replace_uncertain_token(segment.text_raw, best.name),
            final_label=best.name,
            fusion_score=score,
            reasons=reasons,
        )
    if score >= suggest_threshold:
        return Decision(
            status="suggest_only",
            final_text=segment.text_raw,
            final_label=best.name,
            fusion_score=score,
            reasons=reasons,
        )
    return Decision(
        status="kept_original",
        final_text=segment.text_raw,
        final_label=None,
        fusion_score=score,
        reasons=reasons or ["insufficient evidence"],
    )
