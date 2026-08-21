from pathlib import Path

from src.voiceprints import VoiceprintStore, cosine_similarity


def test_cosine_similarity():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_voiceprint_enroll_save_load_and_match(tmp_path: Path):
    path = tmp_path / "voices.json"
    store = VoiceprintStore.load(path)
    store.enroll("Carrie", [1.0, 0.0, 0.0])
    store.enroll("Saul", [0.0, 1.0, 0.0])
    store.save()
    reloaded = VoiceprintStore.load(path)
    match = reloaded.match([0.99, 0.01, 0.0], min_score=0.8, min_margin=0.1)
    assert match is not None
    assert match.name == "Carrie"
