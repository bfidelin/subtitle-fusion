from __future__ import annotations

from pathlib import Path

import yaml

from src.exporters import export_ass, export_compliance_report, export_json, export_srt
from src.fusion import resolve_segment
from src.imdb_index import IMDbIndex
from src.models import MediaContext, PipelineResult, Segment, SpeakerTurn, Word
from src.netflix_style import NetflixStyle, apply_netflix_style, validate_result
from src.scoring import load_scoring_config, segment_needs_review
from src.whisperx_provider import WhisperXConfig, WhisperXProvider


def load_settings(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_stub_segments() -> list[Segment]:
    return [
        Segment(
            id=1,
            start=0.0,
            end=2.5,
            speaker_id="Speaker_1",
            text_raw="Murel, on verrouille tout.",
            words=[
                Word(text="Murel", start=0.0, end=0.4, confidence=0.41, flags=["proper_noun_candidate"]),
                Word(text="on", start=0.5, end=0.7, confidence=0.96),
                Word(text="verrouille", start=0.8, end=1.4, confidence=0.95),
                Word(text="tout.", start=1.5, end=1.8, confidence=0.94),
            ],
        )
    ]


def ingest_transcript(
    video_path: Path,
    settings: dict,
) -> tuple[list[Segment], list[SpeakerTurn], dict[str, list[float]], str | None]:
    provider = settings.get("providers", {}).get("asr", "stub")
    if provider == "stub":
        return build_stub_segments(), [], {}, None
    if provider != "whisperx":
        raise ValueError(f"Unsupported ASR provider: {provider!r}")

    whisperx_cfg = WhisperXConfig.from_mapping(settings.get("whisperx"))
    diarization_provider = settings.get("providers", {}).get(
        "diarization", "whisperx_pyannote"
    )
    if diarization_provider in {"none", "disabled", None}:
        whisperx_cfg = WhisperXConfig.from_mapping(
            {**settings.get("whisperx", {}), "diarize": False}
        )
    elif diarization_provider != "whisperx_pyannote":
        raise ValueError(f"Unsupported diarization provider: {diarization_provider!r}")

    run = WhisperXProvider(whisperx_cfg).transcribe(video_path)
    return run.segments, run.speaker_turns, run.speaker_embeddings, run.language


def run_pipeline(
    video_path: Path,
    media: MediaContext,
    output_dir: Path,
    settings_path: Path = Path("config/settings.yaml"),
    scoring_path: Path = Path("config/scoring.yaml"),
    audio_analysis_path: Path = Path("config/audio_analysis.yaml"),
    style_rules_path: Path = Path("config/style_rules.yaml"),
) -> PipelineResult:
    settings = load_settings(settings_path)
    scoring_cfg = load_scoring_config(scoring_path)
    audio_cfg = load_settings(audio_analysis_path)
    style_cfg = load_settings(style_rules_path)
    imdb_dir = Path(settings.get("paths", {}).get("imdb_dir", "data/imdb"))
    imdb = IMDbIndex.from_dir(imdb_dir)

    # Whole-episode ASR + first-class diarization. WhisperX currently supplies
    # Faster-Whisper ASR, word alignment and pyannote Community-1 diarization.
    segments, speaker_turns, speaker_embeddings, language = ingest_transcript(
        video_path,
        settings,
    )

    if media.imdb_title_id:
        title_candidates = (
            imdb.get_characters_for_title(media.imdb_title_id)
            + imdb.get_people_for_title(media.imdb_title_id)
        )
        for seg in segments:
            seg.imdb_candidates = title_candidates

    # TODO: attach fast OCR, shot boundaries, scout-ASR disagreement and audio
    # event/music evidence to the same timestamped evidence timeline.
    # TODO: route only uncertain windows to stronger local re-ASR/review.
    _ = audio_cfg

    for seg in segments:
        if segment_needs_review(seg, scoring_cfg):
            seg.decision = resolve_segment(seg, scoring_cfg)
            seg.text_corrected = seg.decision.final_text
        else:
            seg.text_corrected = seg.text_raw

    netflix_issues = []
    netflix_cfg = style_cfg.get("netflix", {})
    if netflix_cfg.get("enabled", False):
        netflix_style = NetflixStyle.from_mapping(netflix_cfg)
        apply_netflix_style(segments, netflix_style)
        netflix_issues = validate_result(segments, netflix_style)

    result = PipelineResult(
        media=media,
        segments=segments,
        speaker_turns=speaker_turns,
        speaker_embeddings=speaker_embeddings,
        language=language,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    export_json(result, output_dir / "output.debug.json")
    export_srt(result, output_dir / "output.srt")
    export_ass(result, output_dir / "output.ass")
    if netflix_cfg.get("enabled", False):
        export_compliance_report(netflix_issues, output_dir / "output.netflix-report.json")
    return result
