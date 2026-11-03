from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from src.whisper_http_provider import (
    WhisperHttpConfig,
    WhisperHttpProvider,
    normalize_http_segments,
)


def test_normalize_http_segments_keeps_word_scores_and_speakers() -> None:
    segments = normalize_http_segments(
        [
            {
                "start": 1.0,
                "end": 2.0,
                "text": "Bonjour Muriel.",
                "speaker": 0,
                "words": [
                    {"word": "Bonjour", "start": 1.0, "end": 1.4, "probability": 0.97},
                    {"text": "Muriel.", "start": 1.5, "end": 2.0, "confidence": 0.61},
                ],
            }
        ]
    )

    assert segments[0].speaker_id == "Speaker_1"
    assert segments[0].text_raw == "Bonjour Muriel."
    assert segments[0].words[0].confidence == 0.97
    assert segments[0].words[1].confidence == 0.61
    assert segments[0].words[1].speaker_id == "Speaker_1"


def test_normalize_http_segments_drops_incomplete_word_timings() -> None:
    segments = normalize_http_segments(
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


def test_whisper_http_config_from_mapping_filters_unknown_keys() -> None:
    config = WhisperHttpConfig.from_mapping(
        {
            "url": "http://example.test/asr",
            "diarize": True,
            "timeout_sec": 42,
            "unknown": "ignored",
        }
    )

    assert config.url == "http://example.test/asr"
    assert config.diarize is True
    assert config.timeout_sec == 42


def test_provider_parses_fake_json_response(tmp_path: Path) -> None:
    media = tmp_path / "episode.mp4"
    media.write_bytes(b"not really media")

    payload = {
        "language": "en",
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Hello world.",
                "speaker": 1,
                "words": [
                    {"text": "Hello", "start": 0.0, "end": 0.4, "score": 0.9},
                    {"word": "world.", "start": 0.5, "end": 1.0, "score": 0.95},
                ],
            }
        ],
    }

    class FakeResponse(io.BytesIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_exc) -> bool:
            return False

    response = FakeResponse(json.dumps(payload).encode("utf-8"))
    provider = WhisperHttpProvider(
        WhisperHttpConfig(url="http://127.0.0.1:9000", diarize=True)
    )

    with patch("src.whisper_http_provider.urllib.request.urlopen", return_value=response):
        result = provider.transcribe(media)

    assert result.language == "en"
    assert len(result.segments) == 1
    assert result.segments[0].speaker_id == "Speaker_2"
    assert [word.text for word in result.segments[0].words] == ["Hello", "world."]
    assert result.speaker_embeddings == {}
