from __future__ import annotations

from src.audio_music import TrackCandidate


def score_track_candidate(candidate: TrackCandidate) -> float:
    score = 0.0
    if candidate.confidence is not None:
        score += candidate.confidence * 4.0
    if candidate.lyrics_overlap is not None:
        score += candidate.lyrics_overlap * 2.5
    if candidate.fingerprint_score is not None:
        score += candidate.fingerprint_score * 3.0
    if candidate.mood_match is not None:
        score += candidate.mood_match * 1.0
    if candidate.vocal_match is True:
        score += 1.0
    return score


def choose_best_track(candidates: list[TrackCandidate]) -> TrackCandidate | None:
    if not candidates:
        return None
    return max(candidates, key=score_track_candidate)
