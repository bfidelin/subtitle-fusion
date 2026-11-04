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
    assert cues[-1].speaker_id == "1"


def test_same_speaker_sentences_can_merge_or_split_without_losing_words():
    words = [
        {"text": w, "start": i * 0.5, "end": i * 0.5 + 0.4, "speaker_id": "0"}
        for i, w in enumerate(["I", "left", "the", "ship", "immediately.", "She", "agreed."])
    ]
    cues = segment_words(words)
    assert sum(len(cue.text_raw.split()) for cue in cues) == len(words)


def test_e03_cold_open_example():
    words = [
        {"text": "Really,", "start": 11.24, "end": 11.72, "speaker_id": "0"},
        {"text": "really", "start": 11.92, "end": 12.18, "speaker_id": "0"},
        {"text": "good.", "start": 12.18, "end": 12.54, "speaker_id": "1"},
    ]
    cues = segment_words(words)
    print([(x.speaker_id, x.text_raw) for x in cues])
    assert sum(len(x.text_raw.split()) for x in cues) == 3


def test_sentence_mode_keeps_really_good_whole():
    from src.phrase_segmentation import segment_sentences

    words = [
        {"text": "Really,", "start": 11.24, "end": 11.72, "speaker_id": "0"},
        {"text": "really", "start": 11.92, "end": 12.18, "speaker_id": "0"},
        {"text": "good.", "start": 12.18, "end": 12.54, "speaker_id": "1"},
    ]
    cues = segment_sentences(words)
    assert len(cues) == 1
    assert cues[0].text_raw == "Really, really good."
    assert cues[0].speaker_id == "1"
    assert "multi_speaker_cue" in cues[0].concerns


def test_sentence_mode_splits_sentences_not_speaker_turns():
    from src.phrase_segmentation import segment_sentences

    words = [
        {"text": "Previously", "start": 5.38, "end": 5.8, "speaker_id": "0"},
        {"text": "on", "start": 5.8, "end": 6.22, "speaker_id": "0"},
        {"text": "Below", "start": 6.22, "end": 6.42, "speaker_id": "0"},
        {"text": "Deck.", "start": 6.42, "end": 6.78, "speaker_id": "0"},
        {"text": "Welcome", "start": 6.68, "end": 7.76, "speaker_id": "1"},
        {"text": "to", "start": 7.92, "end": 8.08, "speaker_id": "1"},
        {"text": "Thailand.", "start": 8.08, "end": 8.36, "speaker_id": "1"},
    ]
    cues = segment_sentences(words)
    assert [cue.text_raw for cue in cues] == ["Previously on Below Deck.", "Welcome to Thailand."]


def test_sentence_mode_splits_on_large_pause_without_punctuation():
    from src.phrase_segmentation import segment_sentences

    words = [
        {"text": "Previously", "start": 5.42, "end": 5.984, "speaker_id": "Speaker_1"},
        {"text": "on", "start": 6.165, "end": 6.286, "speaker_id": "Speaker_1"},
        {"text": "Below", "start": 6.286, "end": 6.508, "speaker_id": "Speaker_1"},
        {"text": "Deck", "start": 6.508, "end": 6.789, "speaker_id": "Speaker_1"},
        {"text": "Welcome", "start": 7.736, "end": 8.058, "speaker_id": "Speaker_2"},
        {"text": "to", "start": 8.058, "end": 8.139, "speaker_id": "Speaker_2"},
        {"text": "Thailand,", "start": 8.139, "end": 8.36, "speaker_id": "Speaker_2"},
    ]
    cues = segment_sentences(words)
    assert [cue.text_raw for cue in cues] == ["Previously on Below Deck", "Welcome to Thailand,"]
    assert [cue.speaker_id for cue in cues] == ["Speaker_1", "Speaker_2"]
