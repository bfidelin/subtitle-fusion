from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


GUARDED_PHRASES = {
    ("below", "deck"),
    ("blow", "deck"),
    ("de", "paris"),
    ("the", "ship"),
}


@dataclass(slots=True)
class PhraseCue:
    id: int
    start: float
    end: float
    speaker_id: str
    text_raw: str
    words: list[dict[str, Any]] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def _word_text(word):
    if isinstance(word, Mapping):
        return str(word.get("text", "") or "").strip()
    return str(getattr(word, "text", "") or "").strip()


def _word_start(word):
    if isinstance(word, Mapping):
        return float(word.get("start", 0.0))
    return float("0.0" if getattr(word, "start", None) is None else getattr(word, "start", 0.0))


def _word_end(word):
    if isinstance(word, Mapping):
        return float(word.get("end", word.get("start", 0.0)))
    return float(getattr(word, "end", getattr(word, "start", 0.0)))


def _word_speaker(word):
    value = None
    if isinstance(word, Mapping):
        value = word.get("speaker_id")
        if value is None:
            value = word.get("speaker")
    else:
        value = getattr(word, "speaker_id", None)
        if value is None:
            value = getattr(word, "speaker", None)
    return "UNKNOWN" if value is None else str(value)


def words_to_records(words):
    out = []
    for word in words or []:
        if isinstance(word, Mapping):
            item = dict(word)
        else:
            item = {
                "text": _word_text(word),
                "start": _word_start(word),
                "end": _word_end(word),
                "speaker_id": _word_speaker(word),
            }
            try:
                if hasattr(word, "confidence") and getattr(word, "confidence", None) is not None:
                    item["confidence"] = float(word.confidence)
            except (TypeError, ValueError, AttributeError):
                pass
            try:
                if hasattr(word, "flags"):
                    item["flags"] = list(word.flags)
            except (TypeError, AttributeError):
                pass
        item.setdefault("text", _word_text(word))
        item.setdefault("start", _word_start(word))
        item.setdefault("end", _word_end(word))
        item.setdefault("speaker_id", _word_speaker(word))
        out.append(item)
    return out


def _punctuation_score(text):
    stripped = str(text or "").rstrip()
    last = stripped[-1:] if stripped else ""
    if last in ".?!":
        return 10.0
    if last == ",":
        return 5.0
    if last in "-:;":
        return 3.0
    return 0.0


def _cue_quality(words, max_chars, max_duration):
    if not words:
        return 100.0, ["empty_span"]
    start = float(words[0].get("start", 0.0))
    end = float(words[-1].get("end", start))
    duration = max(0.0, end - start)
    text = " ".join(str(w.get("text", "")).strip() for w in words)
    chars = len(text)
    speakers = {str(w.get("speaker_id", "UNKNOWN")) for w in words}
    issues = []
    cost = 6.0 + 0.005 * chars
    if chars < 8:
        cost += 20.0
        issues.append("orphan_text")
    if chars > max_chars:
        cost += 45.0
        issues.append("too_long")
    if duration < 0.35:
        cost += 25.0
        issues.append("too_short")
    if duration > max_duration:
        cost += 25.0
        issues.append("too_wide")
    if len(words) < 2:
        cost += 6.0
        issues.append("one_word")
    if len(speakers) > 1:
        cost += 500.0
        issues.append("multi_speaker")
    return cost, issues


def _pair_guarded(prev, nxt):
    return (str(prev).lower(), str(nxt).lower()) in GUARDED_PHRASES


def _boundary_bias(words_before, next_word):
    if not words_before or next_word is None:
        return 0.0
    prev = words_before[-1]
    bias = 10.0
    if str(prev.get("speaker_id")) != str(next_word.get("speaker_id")):
        bias -= 40.0
    else:
        bias += 6.0
    punct_value = str(prev.get("text", "")).rstrip()
    if punct_value and punct_value[-1] in ".?!":
        bias -= 10.0
    elif punct_value and punct_value[-1] == ",":
        bias -= 6.0
    gap = float(next_word.get("start", 0.0)) - float(prev.get("end", 0.0))
    if gap >= 0.35:
        bias -= 7.0
    elif gap >= 0.18:
        bias -= 3.0
    elif gap < 0.05:
        bias += 1.0
    prev_word = str(prev.get("text", "")).lower().rstrip(".,!?-_\"'")
    if prev_word in {"below", "the", "a", "an", "de", "la", "of", "and"}:
        bias += 15.0
    next_word_text = str(next_word.get("text", "")).lower()
    if _pair_guarded(prev_word, next_word_text):
        bias += 25.0
    return bias


def _dp_best(words, max_words, max_chars, max_duration):
    n = len(words)
    INF = 10**9
    dp = [INF] * (n + 1)
    parent = [-1] * (n + 1)
    dp[0] = 0.0

    # Build DP in end-index order so each predecessor is already known.
    for end in range(1, n + 1):
        start_begin = max(0, end - max_words)
        for start in range(start_begin, end):
            chunk = words[start:end]
            cost, _issues = _cue_quality(chunk, max_chars, max_duration)
            transition = 0.0
            if end < n:
                transition = _boundary_bias(chunk, words[end])
            total = dp[start] + cost + transition
            if dp[start] < INF and total < dp[end]:
                dp[end] = total
                parent[end] = start

    if dp[n] >= INF:
        return list(range(1, n + 1))
    cuts = []
    pos = n
    while pos > 0 and parent[pos] >= 0:
        cuts.append(parent[pos])
        prior = parent[pos]
        if prior <= 0:
            break
        pos = prior
    if pos > 0:
        cuts.append(pos)
    cuts = sorted(cut for cut in set(cuts) if cut not in (0, n))
    # Include the final boundary to guarantee full coverage.
    if n not in cuts:
        cuts.append(n)
    return [cut for cut in sorted(set(cuts)) if 0 < cut < n] + ([n] if n > 0 else [])


def segment_words(
    words, *, turns=None, max_words=16, max_chars=84, max_duration=8.0, min_turn_gap=0.0
):
    records = words_to_records(words)
    n = len(records)
    reliable_turns = None
    if turns:
        reliable_turns = [
            turn
            for turn in turns
            if float(turn.get("end", 0.0)) - float(turn.get("start", 0.0)) >= float(min_turn_gap)
        ] or list(turns)
    ordered = sorted(
        reliable_turns or (turns if turns else []), key=lambda t: float(t.get("start", 0.0))
    )
    if turns is not None and ordered:
        for item in records:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
            best = None
            best_overlap = -1.0
            for turn in ordered:
                turn_start = float(turn.get("start", 0.0))
                turn_end = float(turn.get("end", turn_start))
                overlap = min(end, turn_end) - max(start, turn_start)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best = turn
            if best is not None and best_overlap > 0.0:
                item["speaker_id"] = str(best.get("speaker", item.get("speaker_id", "UNKNOWN")))
            else:
                item["speaker_id"] = "UNKNOWN"
    if n == 0:
        return []
    records.sort(key=lambda item: float(item.get("start", 0.0)))
    boundaries = _dp_best(records, max_words, max_chars, max_duration)
    cuts = [cut for cut in boundaries if 0 < cut < n]
    cues = []
    last_index = 0
    for cut in cuts:
        end = min(max(last_index + 1, cut), n)
        chunk = records[last_index:end]
        if not chunk:
            continue
        speakers = {str(w.get("speaker_id", "UNKNOWN")) for w in chunk}
        concern = []
        quality, issues = _cue_quality(chunk, max_chars, max_duration)
        if len(speakers) > 1:
            concern.append("multi_speaker_cue")
        prev = records[last_index - 1] if last_index > 0 else None
        if prev is not None and str(prev.get("speaker_id")) != str(chunk[0].get("speaker_id")):
            concern.append("speaker_boundary")
        flag = (
            "uncertain_boundary"
            if any("multi" in c or "speaker_boundary" in c for c in concern)
            else ("quality_issue" if issues else None)
        )
        speaker_id = sorted(speakers)[0] if len(speakers) == 1 else "+".join(sorted(speakers))
        cue = PhraseCue(
            id=len(cues) + 1,
            start=float(chunk[0].get("start", 0.0)),
            end=float(chunk[-1].get("end", chunk[-1].get("start", 0.0))),
            speaker_id=speaker_id,
            text_raw=" ".join(str(w.get("text", "")).strip() for w in chunk).strip(),
            words=list(chunk),
            concerns=concern,
            flags=[flag] if flag else [],
        )
        cues.append(cue)
        last_index = end
    if last_index < n:
        tail = records[last_index:]
        if tail:
            speakers = {str(w.get("speaker_id", "UNKNOWN")) for w in tail}
            speaker_id = sorted(speakers)[0] if len(speakers) == 1 else "+".join(sorted(speakers))
            cues.append(
                PhraseCue(
                    id=len(cues) + 1,
                    start=float(tail[0].get("start", 0.0)),
                    end=float(tail[-1].get("end", tail[-1].get("start", 0.0))),
                    speaker_id=speaker_id,
                    text_raw=" ".join(str(w.get("text", "")).strip() for w in tail).strip(),
                    words=list(tail),
                    flags=["quality_issue"]
                    if (float(tail[-1].get("end", 0.0)) - float(tail[0].get("start", 0.0)))
                    > max_duration
                    else [],
                )
            )
    for idx, cue in enumerate(cues, start=1):
        cue.id = idx
    return cues


def _is_sentence_end(text: str) -> bool:
    value = str(text or "").strip().rstrip("\"'”’)")
    return bool(value) and value[-1] in ".?!"


def segment_sentences(words, *, turns=None, max_chars=84, max_duration=8.0):
    """WhisperX-style sentence cues, then speaker attribution."""
    records = words_to_records(words)
    if turns:
        # Reuse the same overlap-based word/speaker mapping, but never
        # split a sentence because of a turn boundary here.
        build_turn_speaker_map(records, turns)
    n = len(records)
    if n == 0:
        return []
    records.sort(key=lambda item: float(item.get("start", 0.0)))
    groups = []
    current = []
    for word in records:
        if current:
            gap = float(word.get("start", 0.0)) - float(current[-1].get("end", 0.0))
            if gap > 1.2:
                groups.append(current)
                current = []
        current.append(word)
        text = " ".join(str(w.get("text", "")).strip() for w in current)
        duration = float(current[-1].get("end", 0.0)) - float(current[0].get("start", 0.0))
        if (
            _is_sentence_end(word.get("text", ""))
            or len(text) >= max_chars
            or duration >= max_duration
        ):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    cues = []
    for group in groups:
        speakers = [str(w.get("speaker_id", "UNKNOWN")) for w in group]
        unique = sorted(set(speakers))
        if len(unique) == 1:
            speaker_id = unique[0]
        else:
            # Preserve the phrase as one editorial cue. Attribute it to the
            # final speaker (the phrase's completion), and keep per-word IDs.
            tail_speaker = next(
                (s for s in reversed(speakers) if s not in ("", "UNKNOWN")), "UNKNOWN"
            )
            speaker_id = tail_speaker
        cues.append(
            PhraseCue(
                id=len(cues) + 1,
                start=float(group[0].get("start", 0.0)),
                end=float(group[-1].get("end", group[-1].get("start", 0.0))),
                speaker_id=speaker_id,
                text_raw=" ".join(str(w.get("text", "")).strip() for w in group).strip(),
                words=list(group),
                concerns=["multi_speaker_cue"] if len(unique) > 1 else [],
                flags=["mixed_speakers"] if len(unique) > 1 else [],
            )
        )
    for idx, cue in enumerate(cues, start=1):
        cue.id = idx
    return cues


def build_turn_speaker_map(records, turns):
    """Assign each word a speaker by maximum turn overlap."""
    ordered = sorted(turns or [], key=lambda t: float(t.get("start", 0.0)))
    for item in records:
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start))
        best = None
        best_overlap = -1.0
        for turn in ordered:
            turn_start = float(turn.get("start", 0.0))
            turn_end = float(turn.get("end", turn_start))
            overlap = min(end, turn_end) - max(start, turn_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best = turn
        if best is not None and best_overlap > 0.0:
            item["speaker_id"] = str(best.get("speaker", item.get("speaker_id", "UNKNOWN")))
        elif str(item.get("speaker_id", "")) in ("", "UNKNOWN"):
            item["speaker_id"] = "UNKNOWN"
