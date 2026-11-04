from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse()
    import speakrs

    work = Path("/home/calmos/tmp/speakrs")
    work.mkdir(parents=True, exist_ok=True)
    wav_path = work / "input.wav"
    cp = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-i",
            str(args.audio),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0 or not wav_path.is_file():
        raise RuntimeError(f"ffmpeg extraction failed: {cp.stderr[-300:]}")

    pipeline = speakrs.Pipeline.from_pretrained(args.mode)
    result = pipeline.diarize_file(str(wav_path))
    labels: list[str] = []
    for segment in result.segments:
        label = str(segment.speaker)
        if label not in labels:
            labels.append(label)
    mapped = {label: f"Speaker_{index + 1}" for index, label in enumerate(labels)}
    turns = [
        {
            "start": float(segment.start),
            "end": float(segment.end),
            "speaker": mapped[str(segment.speaker)],
        }
        for segment in result.segments
    ]
    payload = {"speaker_turns": turns, "speaker_embeddings": {}}
    Path(args.output).write_text(json.dumps(payload), encoding="utf-8")
    print(json.dumps({"turns": len(turns), "speakers": len(labels)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
