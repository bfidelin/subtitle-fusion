from __future__ import annotations

from pathlib import Path

import yaml

from src.exporters import export_ass, export_json, export_srt
from src.fusion import resolve_segment
from src.imdb_index import IMDbIndex
from src.models import MediaContext, PipelineResult, Segment, Word
from src.scoring import load_scoring_config, segment_needs_review


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


def run_pipeline(
    video_path: Path,
    media: MediaContext,
    output_dir: Path,
    settings_path: Path = Path("config/settings.yaml"),
    scoring_path: Path = Path("config/scoring.yaml"),
) -> PipelineResult:
    _ = video_path
    settings = load_settings(settings_path)
    scoring_cfg = load_scoring_config(scoring_path)
    imdb_dir = Path(settings.get("paths", {}).get("imdb_dir", "data/imdb"))
    imdb = IMDbIndex.from_dir(imdb_dir)

    segments = build_stub_segments()
    if media.imdb_title_id:
        title_candidates = imdb.get_characters_for_title(media.imdb_title_id) + imdb.get_people_for_title(media.imdb_title_id)
        for seg in segments:
            seg.imdb_candidates = title_candidates

    for seg in segments:
        if segment_needs_review(seg, scoring_cfg):
            seg.decision = resolve_segment(seg, scoring_cfg)
            seg.text_corrected = seg.decision.final_text
        else:
            seg.text_corrected = seg.text_raw

    result = PipelineResult(media=media, segments=segments)
    output_dir.mkdir(parents=True, exist_ok=True)
    export_json(result, output_dir / "output.debug.json")
    export_srt(result, output_dir / "output.srt")
    export_ass(result, output_dir / "output.ass")
    return result
