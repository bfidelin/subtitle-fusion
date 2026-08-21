from src.media_preflight import parse_ffprobe


def test_parse_ffprobe_classifies_subtitle_streams() -> None:
    inventory = parse_ffprobe(
        {
            "format": {"duration": "2700.5", "format_name": "matroska,webm"},
            "streams": [
                {"index": 0, "codec_type": "video", "codec_name": "h264"},
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "tags": {"language": "fra"},
                    "disposition": {"default": 1},
                },
                {
                    "index": 2,
                    "codec_type": "subtitle",
                    "codec_name": "subrip",
                    "tags": {"language": "fra", "title": "French SDH"},
                    "disposition": {"default": 1, "forced": 0},
                },
                {
                    "index": 3,
                    "codec_type": "subtitle",
                    "codec_name": "hdmv_pgs_subtitle",
                    "tags": {"language": "eng"},
                },
            ],
        }
    )

    assert inventory.duration_sec == 2700.5
    assert len(inventory.audio_streams) == 1
    assert [stream.index for stream in inventory.text_subtitle_streams] == [2]
    assert [stream.index for stream in inventory.image_subtitle_streams] == [3]
    assert inventory.preferred_text_subtitle("fra").index == 2


def test_preferred_text_subtitle_returns_none_when_absent() -> None:
    inventory = parse_ffprobe({"streams": [{"index": 0, "codec_type": "video"}]})
    assert inventory.preferred_text_subtitle("fra") is None
