from src.models import MediaContext, Segment, SpeakerTurn, Word
from src.pipeline import run_pipeline


def test_run_pipeline_runs_phrase_segmentation_with_turns(monkeypatch, tmp_path):
    fake_video = tmp_path / "fake_e03.mkv"
    fake_video.write_bytes(b"x")
    fake_segment = Segment(
        id=1,
        start=1.0,
        end=1.9,
        speaker_id="0",
        text_raw="I know. Really?",
        words=[
            Word(text="I", start=1.0, end=1.2, confidence=1.0, speaker_id="0"),
            Word(text="know.", start=1.2, end=1.5, confidence=1.0, speaker_id="0"),
            Word(text="Really?", start=1.6, end=1.9, confidence=1.0, speaker_id="1"),
        ],
    )
    fake_turns = [
        SpeakerTurn(start=1.0, end=1.5, speaker_id="0"),
        SpeakerTurn(start=1.6, end=1.9, speaker_id="1"),
    ]
    import src.pipeline as pipeline_module

    monkeypatch.setattr(
        pipeline_module,
        "ingest_transcript",
        lambda video_path, settings: ([fake_segment], fake_turns, {}, None),
    )
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "pipeline:\n  enable_phrase_segmentation: true\n  enable_ocr: false\n  enable_media_preflight: false\n  write_debug_json: true\n",
        encoding="utf-8",
    )
    res = run_pipeline(
        video_path=fake_video,
        media=MediaContext(title="X", season=1, episode=1),
        output_dir=tmp_path / "out",
        settings_path=settings_path,
    )
    assert res.meta.get("phrase_segmentation", {}).get("error") is None
    assert res.meta["phrase_segmentation"].get("ran") is True
    assert len(res.segments) >= 2
    assert res.segments[0].speaker_id == "0"
    assert res.segments[-1].speaker_id == "1"
