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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        media = MediaContext(
            title=args.title,
            season=args.season,
            episode=args.episode,
            imdb_title_id=args.imdb_title_id,
        )
        run_pipeline(
            video_path=args.video,
            media=media,
            output_dir=args.output_dir,
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
