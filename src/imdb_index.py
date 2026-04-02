from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from src.models import Candidate, MediaContext


@dataclass(slots=True)
class IMDbIndex:
    basics: dict[str, dict[str, str]] = field(default_factory=dict)
    principals: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    names: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_dir(cls, imdb_dir: Path) -> "IMDbIndex":
        index = cls()
        basics_path = imdb_dir / "title.basics.tsv"
        principals_path = imdb_dir / "title.principals.tsv"
        names_path = imdb_dir / "name.basics.tsv"

        if basics_path.exists():
            index.basics = _read_tsv_by_key(basics_path, "tconst")
        if names_path.exists():
            index.names = _read_tsv_by_key(names_path, "nconst")
        if principals_path.exists():
            with principals_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                for row in reader:
                    index.principals.setdefault(row["tconst"], []).append(row)
        return index

    def get_people_for_title(self, title_id: str) -> list[Candidate]:
        people: list[Candidate] = []
        for row in self.principals.get(title_id, []):
            nconst = row.get("nconst", "")
            name = self.names.get(nconst, {}).get("primaryName", nconst)
            people.append(Candidate(type="actor", name=name, score=0.0, meta=row))
        return people

    def get_characters_for_title(self, title_id: str) -> list[Candidate]:
        characters: list[Candidate] = []
        for row in self.principals.get(title_id, []):
            raw = row.get("characters") or ""
            cleaned = raw.strip().strip('[]')
            if not cleaned or cleaned == "\\N":
                continue
            for chunk in cleaned.split(","):
                name = chunk.strip().strip('"')
                if name:
                    characters.append(Candidate(type="character", name=name, score=0.0, meta=row))
        return characters

    def get_title_candidates(self, media: MediaContext) -> list[Candidate]:
        if media.imdb_title_id and media.imdb_title_id in self.basics:
            row = self.basics[media.imdb_title_id]
            return [Candidate(type="title", name=row.get("primaryTitle", ""), score=1.0, meta=row)]
        return []


def _read_tsv_by_key(path: Path, key: str) -> dict[str, dict[str, str]]:
    results: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            results[row[key]] = row
    return results
