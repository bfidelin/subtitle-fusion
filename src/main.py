from __future__ import annotations

import argparse
from pathlib import Path

from src.models import MediaContext
from src.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="subtitle-fusion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run subtitle fusion pipeline")
    run_parser.add_argument("--video", type=Path, required=True)
    run_parser.add_argument("--title", type=str, default=None)
    run_parser.add_argument("--season", type=int, default=None)
    run_parser.add_argument("--episode", type=int, default=None)
    run_parser.add_argument("--imdb-title-id", type=str, default=None)
    run_parser.add_argument("--output-dir", type=Path, required=True)
    run_parser.add_argument("--speaker-map", type=Path, default=None, help="YAML mapping of diarization IDs to character names; enrolled as voiceprints")
    run_parser.add_argument("--settings", type=Path, default=Path("config/settings.yaml"))
    run_parser.add_argument("--audio-config", type=Path, default=Path("config/audio_analysis.yaml"))
    run_parser.add_argument("--style-config", type=Path, default=Path("config/style_rules.yaml"))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        media = MediaContext(title=args.title, season=args.season, episode=args.episode, imdb_title_id=args.imdb_title_id)
        run_pipeline(video_path=args.video, media=media, output_dir=args.output_dir, settings_path=args.settings, audio_analysis_path=args.audio_config, style_path=args.style_config, speaker_map_path=args.speaker_map)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
