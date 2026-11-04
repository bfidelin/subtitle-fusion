from src.phrase_segmentation import segment_words


def test_preserves_all_words_and_places_cold_open_boundary():
    words = [
        {"text": "Previously", "start": 5.38, "end": 5.80, "speaker_id": "0"},
        {"text": "on", "start": 5.80, "end": 6.22, "speaker_id": "0"},
        {"text": "Below", "start": 6.22, "end": 6.42, "speaker_id": "0"},
        {"text": "Deck", "start": 6.42, "end": 6.68, "speaker_id": "0"},
        {"text": "Welcome", "start": 6.68, "end": 7.76, "speaker_id": "1"},
        {"text": "to", "start": 7.92, "end": 8.08, "speaker_id": "1"},
        {"text": "Thailand,", "start": 8.08, "end": 8.36, "speaker_id": "1"},
    ]
    cues = segment_words(words)
    flat = [w for cue in cues for w in cue.text_raw.split()]
    assert flat == [word["text"] for word in words]
    assert cues[0].text_raw == "Previously on Below Deck"
    assert "Welcome to Thailand," in cues[1].text_raw


def test_cross_speaker_dialogue_does_not_merge_speakers():
    words = [
        {"text": "I", "start": 1.0, "end": 1.2, "speaker_id": "0"},
        {"text": "know.", "start": 1.2, "end": 1.5, "speaker_id": "0"},
        {"text": "Really?", "start": 1.6, "end": 1.9, "speaker_id": "1"},
    ]
    cues = segment_words(words)
    assert len(cues) >= 2
    assert cues[0].speaker_id == "0"
    assert cues[1].speaker_id == "1"
    assert all("multi_speaker_cue" not in cue.concerns for cue in cues)


def test_same_speaker_sentences_can_merge_or_split_without_losing_words():
    words = [
        {"text": w, "start": i * 0.5, "end": i * 0.5 + 0.4, "speaker_id": "0"}
        for i, w in enumerate(["I", "left", "the", "ship", "immediately.", "She", "agreed."])
    ]
    cues = segment_words(words)
    assert sum(len(cue.text_raw.split()) for cue in cues) == len(words)
