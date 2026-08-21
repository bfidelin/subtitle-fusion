from src.audio_music import AudioEvent, merge_adjacent_events


def test_merge_adjacent_events_same_label() -> None:
    merged = merge_adjacent_events(
        [
            AudioEvent("Door", 0.7, 1.0, 2.0),
            AudioEvent("Door", 0.9, 2.5, 3.0),
            AudioEvent("Siren", 0.8, 10.0, 11.0),
        ],
        max_gap=1.0,
    )

    assert [(event.label, event.start, event.end) for event in merged] == [
        ("Door", 1.0, 3.0),
        ("Siren", 10.0, 11.0),
    ]
    assert merged[0].score == 0.9
