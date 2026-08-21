from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class VoiceMatch:
    name: str
    score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _centroid(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    width = len(vectors[0])
    valid = [vector for vector in vectors if len(vector) == width]
    if not valid:
        return []
    return [sum(vector[i] for vector in valid) / len(valid) for i in range(width)]


def series_key(title: str | None) -> str:
    raw = (title or "unknown-series").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return value or "unknown-series"


class VoiceprintStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, dict[str, Any]] = {}

    @classmethod
    def load(cls, path: Path) -> "VoiceprintStore":
        store = cls(path)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            store.data = raw.get("characters", {})
        return store

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "characters": self.data}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def enroll(self, name: str, embedding: list[float]) -> None:
        if not embedding:
            return
        record = self.data.setdefault(name, {"samples": [], "centroid": []})
        samples: list[list[float]] = record.setdefault("samples", [])
        samples.append([float(value) for value in embedding])
        if len(samples) > 12:
            samples[:] = samples[-12:]
        record["centroid"] = _centroid(samples)

    def match(self, embedding: list[float], *, min_score: float = 0.78, min_margin: float = 0.04) -> VoiceMatch | None:
        scored: list[VoiceMatch] = []
        for name, record in self.data.items():
            centroid = record.get("centroid") or _centroid(record.get("samples", []))
            scored.append(VoiceMatch(name=name, score=cosine_similarity(embedding, centroid)))
        if not scored:
            return None
        scored.sort(key=lambda item: item.score, reverse=True)
        best = scored[0]
        second = scored[1].score if len(scored) > 1 else -1.0
        if best.score < min_score or best.score - second < min_margin:
            return None
        return best
