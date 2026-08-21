from __future__ import annotations

from src.whisperx_provider import (
    WhisperXConfig,
    attach_overlap_evidence,
    build_speaker_turns,
    normalize_whisperx_segments,
)


def test_normalize_whisperx_segments_keeps_word_scores_and_speakers() -> None:
    segments = normalize_whisperx_segments(
        [
            {
                "start": 1.0,
                "end": 2.0,
                "text": " Bonjour Muriel.",
                "speaker": "SPEAKER_01",
                "words": [
                    {
                        "word": "Bonjour",
                        "start": 1.0,
                        "end": 1.4,
                        "score": 0.97,
                        "speaker": "SPEAKER_01",
                    },
                    {
                        "word": "Muriel.",
                        "start": 1.5,
                        "end": 2.0,
                        "score": 0.61,
                        "speaker": "SPEAKER_01",
                    },
                ],
            }
        ]
    )

    assert segments[0].speaker_id == "SPEAKER_01"
    assert segments[0].text_raw == "Bonjour Muriel."
    assert segments[0].words[1].confidence == 0.61
    assert segments[0].words[1].speaker_id == "SPEAKER_01"


def test_missing_word_alignment_is_not_faked() -> None:
    segments = normalize_whisperx_segments(
        [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "2014.",
                "words": [{"word": "2014.", "score": 0.8}],
            }
        ]
    )

    assert segments[0].text_raw == "2014."
    assert segments[0].words == []


def test_diarization_turns_preserve_overlap_evidence() -> None:
    turns = build_speaker_turns(
        [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 1.5, "end": 2.5, "speaker": "SPEAKER_01"},
        ]
    )

    assert turns[0].overlap_speakers == ["SPEAKER_01"]
    assert turns[1].overlap_speakers == ["SPEAKER_00"]


def test_overlap_evidence_is_attached_to_subtitle_segment() -> None:
    segments = normalize_whisperx_segments(
        [{"start": 1.6, "end": 1.9, "text": "Parlez tous les deux."}]
    )
    turns = build_speaker_turns(
        [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 1.5, "end": 2.5, "speaker": "SPEAKER_01"},
        ]
    )

    attach_overlap_evidence(segments, turns)

    assert segments[0].overlap_speakers == ["SPEAKER_00", "SPEAKER_01"]


def test_config_ignores_unknown_keys() -> None:
    config = WhisperXConfig.from_mapping(
        {
            "model": "small",
            "diarization_model": "pyannote/speaker-diarization-community-1",
            "future_option": "ignored",
        }
    )

    assert config.model == "small"
    assert config.diarization_model.endswith("community-1")
