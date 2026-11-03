from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.models import Candidate


@dataclass(slots=True)
class JellyfinPeopleConfig:
    data_dir: str = "data/people"
    series_name: str | None = None
    suffix: str = "_people.tsv"
    min_confidence: float = 0.7

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "JellyfinPeopleConfig":
        data = data or {}
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


class JellyfinPeopleIndex:
    def __init__(self, rows: list[dict[str, str]]):
        self.rows = rows
        self._by_name = {str(row.get("name", "")).lower(): row for row in rows if row.get("name")}
        self._aliases: dict[str, dict[str, str]] = {}
        for row in rows:
            name = row.get("name", "")
            if not name:
                continue
            self._aliases.setdefault(name.split()[-1].lower(), row)
            self._aliases.setdefault(name.split()[0].lower(), row)

    @classmethod
    def from_paths(cls, paths=None):
        rows = []
        if paths is None:
            paths = sorted(Path("data/people").glob("*_people.tsv")) if Path("data/people").is_dir() else []
        elif isinstance(paths, (str, Path)):
            p = Path(paths)
            if p.is_dir():
                paths = sorted(p.glob("*_people.tsv"))
            elif p.is_file():
                paths = [p]
        else:
            paths = [Path(p) for p in paths]
        for path in paths:
            try:
                with path.open("r", encoding="utf-8", newline="") as handle:
                    for row in csv.DictReader(handle, delimiter="\t"):
                        if row.get("name"):
                            rows.append(row)
            except FileNotFoundError:
                pass
        return cls(rows)

    def _match(self, token: str):
        token = token.strip().strip("-").lower()
        if not token:
            return None
        if token in self._by_name:
            return self._by_name[token]
        if token in self._aliases:
            return self._aliases[token]
        for row in self.rows:
            name = (row.get("name") or "").lower()
            if token == name.split()[-1].lower() or token == name.split()[0].lower():
                return row
        return None

    def candidates_for_tokens(self, tokens: list[str], min_occurrences: int = 1):
        out: list[Candidate] = []
        seen: set[str] = set()
        counts: dict[str, int] = {}
        for token in tokens:
            row = self._match(token)
            if not row or not row.get("name"):
                continue
            name = row.get("name", "").strip()
            counts[name] = counts.get(name, 0) + 1
            if counts[name] < min_occurrences or name.lower() in seen:
                continue
            seen.add(name.lower())
            out.append(
                Candidate(
                    type="jellyfin_person",
                    name=name,
                    score=0.0,
                    meta={"role": row.get("role"), "type": row.get("type"), "image": f"{row.get('image_url','')}", "occurrences": counts[name]},
                )
            )
        return out

    def tokens_from_ocr(self, hits) -> list[str]:
        tokens = []
        for hit in hits:
            text = str(getattr(hit, "text", "") or "")
            for word in re.findall(r"\b[A-Z][a-z]{2,}\b", text):
                if word not in tokens:
                    tokens.append(word)
            for chunk in text.split():
                if chunk.isupper() and len(chunk) >= 3:
                    cap = chunk.lower().capitalize()
                    if cap not in tokens:
                        tokens.append(cap)
        return tokens

    def candidates_for_ocr(self, hits, min_confidence: float = 0.7, min_occurrences: int = 2):
        usable = [h for h in hits if float(getattr(h, "confidence", 1.0) or 0.0) >= min_confidence]
        return self.candidates_for_tokens(self.tokens_from_ocr(usable), min_occurrences=min_occurrences)


def attach_jellyfin_candidates(segments: list, hits: list, index: JellyfinPeopleIndex, min_confidence: float = 0.7):
    for segment in segments:
        nearby = getattr(segment, "ocr_hits", []) or hits
        candidates = index.candidates_for_ocr(nearby, min_confidence=min_confidence)
        seen = {str(getattr(c, "name", "")).lower() for c in segment.imdb_candidates}
        for candidate in candidates:
            if candidate.name.lower() not in seen:
                segment.imdb_candidates.append(candidate)
                seen.add(candidate.name.lower())
