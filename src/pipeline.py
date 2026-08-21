from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import yaml

from src.exporters import export_ass, export_compliance_report, export_json, export_srt
from src.fusion import resolve_segment
from src.imdb_index import IMDbIndex
from src.media_preflight import MediaPreflightError, probe_media
from src.models import MediaContext, PipelineResult, Segment, SpeakerTurn, Word
from src.netflix_style import NetflixStyle, apply_netflix_style, validate_result
from src.scoring import load_scoring_config, segment_needs_review
from src.voiceprints import VoiceprintStore, series_key
from src.whisperx_provider import WhisperXConfig, WhisperXProvider


def load_settings(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_speaker_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return {str(speaker_id): str(name) for speaker_id, name in raw.items() if name}


def build_stub_segments() -> list[Segment]:
    return [
        Segment(
            id=1,
            start=0.0,
            end=2.5,
            speaker_id="Speaker_1",
            text_raw="Murel, on verrouille tout.",
            words=[
                Word(
                    text="Murel",
                    start=0.0,
                    end=0.4,
                    confidence=0.41,
                    flags=["proper_noun_candidate"],
                ),
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


def apply_voiceprints(
    segments: list[Segment],
    speaker_embeddings: dict[str, list[float]],
    media: MediaContext,
    settings: dict,
    speaker_map_path: Path | None,
) -> dict[str, object]:
    cfg = settings.get("voiceprints", {})
    if not cfg.get("enabled", True) or not speaker_embeddings:
        return {"enabled": bool(cfg.get("enabled", True)), "matches": {}}

    store_dir = Path(cfg.get("store_dir", "data/voiceprints"))
    store = VoiceprintStore.load(store_dir / f"{series_key(media.title)}.json")
    speaker_map = load_speaker_map(speaker_map_path)

    enrolled: dict[str, str] = {}
    for speaker_id, name in speaker_map.items():
        embedding = speaker_embeddings.get(speaker_id)
        if not embedding:
            continue
        store.enroll(
            name,
            embedding,
            max_samples=int(cfg.get("max_samples_per_character", 12)),
        )
        enrolled[speaker_id] = name
    if enrolled:
        store.save()

    matches: dict[str, dict[str, object]] = {}
    for speaker_id, embedding in speaker_embeddings.items():
        if speaker_id in enrolled:
            matches[speaker_id] = {"name": enrolled[speaker_id], "score": 1.0, "enrolled": True}
            continue
        match = store.match(
            embedding,
            min_score=float(cfg.get("min_score", 0.78)),
            min_margin=float(cfg.get("min_margin", 0.04)),
        )
        if match:
            matches[speaker_id] = {"name": match.name, "score": match.score, "enrolled": False}

    for segment in segments:
        resolved = matches.get(segment.speaker_id)
        if not resolved:
            continue
        segment.speaker_name_candidate = str(resolved["name"])
        segment.speaker_identity_confidence = float(resolved["score"])

    return {"enabled": True, "enrolled": enrolled, "matches": matches}


def run_pipeline(
    video_path: Path,
    media: MediaContext,
    output_dir: Path,
    settings_path: Path = Path("config/settings.yaml"),
    scoring_path: Path = Path("config/scoring.yaml"),
    audio_analysis_path: Path = Path("config/audio_analysis.yaml"),
    style_rules_path: Path = Path("config/style_rules.yaml"),
    speaker_map_path: Path | None = None,
) -> PipelineResult:
    settings = load_settings(settings_path)
    scoring_cfg = load_scoring_config(scoring_path)
    audio_cfg = load_settings(audio_analysis_path)
    style_cfg = load_settings(style_rules_path)
    imdb_dir = Path(settings.get("paths", {}).get("imdb_dir", "data/imdb"))
    imdb = IMDbIndex.from_dir(imdb_dir)
    meta: dict[str, object] = {}

    if settings.get("pipeline", {}).get("enable_media_preflight", True):
        try:
            inventory = probe_media(video_path)
            if media.duration_sec is None:
                media.duration_sec = inventory.duration_sec
            meta["media_preflight"] = {
                "format_name": inventory.format_name,
                "duration_sec": inventory.duration_sec,
                "streams": [asdict(stream) for stream in inventory.streams],
                "text_subtitle_streams": [stream.index for stream in inventory.text_subtitle_streams],
                "image_subtitle_streams": [stream.index for stream in inventory.image_subtitle_streams],
            }
        except (MediaPreflightError, OSError, ValueError) as exc:
            # Preflight is an optimization/evidence stage; failure must not hide a
            # usable ASR path. Record it for diagnosis and continue.
            meta["media_preflight"] = {"error": str(exc)}

    segments, speaker_turns, speaker_embeddings, language = ingest_transcript(
        video_path,
        settings,
    )
    meta["voiceprints"] = apply_voiceprints(
        segments,
        speaker_embeddings,
        media,
        settings,
        speaker_map_path,
    )

    if media.imdb_title_id:
        title_candidates = (
            imdb.get_characters_for_title(media.imdb_title_id)
            + imdb.get_people_for_title(media.imdb_title_id)
        )
        for seg in segments:
            seg.imdb_candidates = title_candidates

    # Next integrations use the same evidence timeline:
    # - reuse/extract embedded subtitle tracks after quality scoring
    # - shared shot map + sparse OCR
    # - cheap audio scout -> PANNs candidate verification
    # - selective local re-ASR / active-speaker review
    meta["audio_policy"] = {
        "configured": bool(audio_cfg),
        "runtime_wired": False,
        "reason": "scout/verifier cascade is intentionally not run globally yet",
    }

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
        meta=meta,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    export_json(result, output_dir / "output.debug.json")
    export_srt(result, output_dir / "output.srt")
    export_ass(result, output_dir / "output.ass")
    if netflix_cfg.get("enabled", False):
        export_compliance_report(netflix_issues, output_dir / "output.netflix-report.json")
    return result
