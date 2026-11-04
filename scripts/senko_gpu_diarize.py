from __future__ import annotations
import argparse
import json
import subprocess
import time
from pathlib import Path


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse()
    import senko

    tmpdir = Path("/home/calmos/tmp/senko")
    tmpdir.mkdir(parents=True, exist_ok=True)
    wav_path = tmpdir / "analysis.wav"
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

    t0 = time.time()
    result = senko.Diarizer(device="cuda", warmup=True, quiet=True).diarize(
        str(wav_path), generate_colors=False
    )

    labels = []
    turns = []
    for segment in sorted(result.get("merged_segments", []), key=lambda x: (x["start"], x["end"])):
        raw = str(segment.get("speaker"))
        if raw not in labels:
            labels.append(raw)
        turns.append(
            {
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "speaker": f"Speaker_{labels.index(raw)+1}",
            }
        )

    centroids = result.get("speaker_centroids", {})
    embeddings = {}
    for index, label in enumerate(labels):
        centroid = centroids.get(label)
        try:
            centroid_list = centroid.tolist() if hasattr(centroid, "tolist") else list(centroid)
        except Exception:
            centroid_list = None
        if centroid_list:
            embeddings[f"Speaker_{index + 1}"] = [float(x) for x in centroid_list]

    payload = {"speaker_turns": turns, "speaker_embeddings": embeddings}
    Path(args.output).write_text(json.dumps(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "turns": len(turns),
                "speakers": len(labels),
                "embeddings": len(embeddings),
                "seconds": round(time.time() - t0, 2),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
