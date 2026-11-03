from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

for dotenv in ("/home/calmos/.env", "/home/calmos/subtitle-fusion/.env"):
    try:
        for line in Path(dotenv).read_text().splitlines():
            line = line.strip()
            if line.startswith("HF_TOKEN=") and not os.environ.get("HF_TOKEN"):
                os.environ["HF_TOKEN"] = line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Pyannote GPU diarization helper")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-speakers", dest="min_speakers", type=int, default=None)
    parser.add_argument("--max-speakers", dest="max_speakers", type=int, default=None)
    args = parser.parse_args()

    import torch

    pipeline_kwargs = {}
    if args.min_speakers is not None:
        pipeline_kwargs["min_speakers"] = args.min_speakers
    if args.max_speakers is not None:
        pipeline_kwargs["max_speakers"] = args.max_speakers

    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1", token=os.environ.get("HF_TOKEN")
    )
    pipeline.to(torch.device("cuda"))

    audio_path = args.audio
    if not str(audio_path).lower().endswith(".wav"):
        import subprocess, tempfile
        wav_path = Path(tempfile.mkdtemp()) / "input.wav"
        cp = subprocess.run(
            ["ffmpeg", "-y", "-nostdin", "-i", str(audio_path), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path)],
            capture_output=True, text=True,
        )
        if cp.returncode != 0 or not wav_path.is_file() or wav_path.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg extraction failed: {cp.stderr[-300:]}")
        audio_path = str(wav_path)

    result = pipeline(audio_path, **pipeline_kwargs)
    diarization = result.speaker_diarization
    embeddings = getattr(result, "speaker_embeddings", None)

    labels: list[str] = []
    for _, _, label in diarization.itertracks(yield_label=True):
        if label not in labels:
            labels.append(label)

    mapped_labels = {label: f"Speaker_{index + 1}" for index, label in enumerate(labels)}

    turns = []
    for segment, _, label in diarization.itertracks(yield_label=True):
        turns.append(
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "speaker": mapped_labels.get(label, "Speaker_0"),
            }
        )

    embedding_map: dict[str, list[float]] = {}
    if embeddings is not None:
        try:
            for index, label in enumerate(labels):
                mapped = mapped_labels[label]
                embedding_map[mapped] = [float(x) for x in embeddings[index].ravel().tolist()]
        except Exception:
            pass

    Path(args.output).write_text(
        json.dumps({"speaker_turns": turns, "speaker_embeddings": embedding_map})
    )
    print(json.dumps({"turns": len(turns), "speakers": len(labels), "embeddings": len(embedding_map)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
