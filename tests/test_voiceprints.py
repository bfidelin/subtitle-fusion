from pathlib import Path

from src.voiceprints import VoiceprintStore, cosine_similarity, series_key


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_series_key() -> None:
    assert series_key("The Handmaid's Tale") == "the-handmaid-s-tale"


def test_voiceprint_match_requires_score_and_margin(tmp_path: Path) -> None:
    store = VoiceprintStore(tmp_path / "show.json")
    store.enroll("Alice", [1.0, 0.0, 0.0])
    store.enroll("Bob", [0.0, 1.0, 0.0])

    match = store.match([0.99, 0.01, 0.0], min_score=0.78, min_margin=0.04)
    assert match is not None
    assert match.name == "Alice"

    ambiguous = VoiceprintStore(tmp_path / "ambiguous.json")
    ambiguous.enroll("Alice", [1.0, 0.0])
    ambiguous.enroll("Bob", [0.99, 0.01])
    assert ambiguous.match([1.0, 0.0], min_score=0.5, min_margin=0.04) is None


def test_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "show.json"
    store = VoiceprintStore(path)
    store.enroll("Alice", [1.0, 2.0])
    store.save()

    loaded = VoiceprintStore.load(path)
    assert "Alice" in loaded.data
    assert loaded.data["Alice"]["centroid"] == [1.0, 2.0]
