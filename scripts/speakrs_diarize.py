from __future__ import annotations

import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", default="cuda")
    parser.add_argument("--profile", default="precise", choices=["default", "precise"])
    parser.add_argument("--chunk-sec", type=float, default=0.0)
    parser.add_argument("--overlap-sec", type=float, default=60.0)
    parser.add_argument("--vocals", action="store_true")
    parser.add_argument(
        "--separator-python", default="/home/calmos/miniconda3/envs/senko/bin/python"
    )
    parser.add_argument(
        "--separator-script", default="/home/calmos/subtitle-fusion/scripts/separate_vocals.py"
    )
    return parser.parse_args()


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise RuntimeError("expected 16 kHz mono PCM16 WAV")
        if handle.getframerate() != 16000:
            raise RuntimeError("expected 16 kHz WAV")
        data = handle.readframes(handle.getnframes())
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def make_config(speakrs, profile: str):
    if profile != "precise":
        return None
    return speakrs.PipelineConfig(
        activity=speakrs.ActivityCleanup(min_active_frames=2, max_inactive_gap_frames=2),
        clustering=speakrs.ClusteringConfig(
            ahc=speakrs.AhcConfig(threshold=0.55),
            vbx=speakrs.VbxConfig(
                fa=0.07, fb=0.8, max_iters=20, epsilon=0.0001, init_smoothing=7.0
            ),
            speaker_keep_threshold=1e-7,
        ),
        merge_gap=0.2,
        reconstruct_method="smoothed",
        smoothing_epsilon=0.05,
    )


def local_labels(segments) -> list[str]:
    labels: list[str] = []
    for segment in segments:
        label = str(segment.speaker)
        if label not in labels:
            labels.append(label)
    return labels


def assign_labels(local: list[str], segments, window_start: float, existing, next_id: int):
    mapping: dict[str, str] = {}
    if not existing:
        for label in local:
            mapping[label] = f"Speaker_{next_id}"
            next_id += 1
        return mapping, next_id
    used: set[str] = set()
    scored: list[tuple[float, str, str]] = []
    for label in local:
        best_score = 0.0
        best_global = ""
        for global_label in {turn["speaker"] for turn in existing}:
            score = 0.0
            for segment in segments:
                if str(segment.speaker) != label:
                    continue
                a0 = window_start + float(segment.start)
                a1 = window_start + float(segment.end)
                for turn in existing:
                    if turn["speaker"] != global_label:
                        continue
                    score += overlap(a0, a1, float(turn["start"]), float(turn["end"]))
            if score > best_score:
                best_score = score
                best_global = global_label
        scored.append((best_score, label, best_global))
    for score, label, global_label in sorted(scored, reverse=True):
        if score > 0.15 and global_label and global_label not in used:
            mapping[label] = global_label
            used.add(global_label)
        else:
            mapping[label] = f"Speaker_{next_id}"
            next_id += 1
    return mapping, next_id


def main() -> int:
    args = parse()
    import speakrs

    work = Path("/home/calmos/tmp/speakrs")
    work.mkdir(parents=True, exist_ok=True)
    wav_path = work / "input.wav"
    if args.vocals:
        wav_path = work / "vocals.wav"
        cp = subprocess.run(
            [
                args.separator_python,
                args.separator_script,
                "--audio",
                str(args.audio),
                "--output",
                str(wav_path),
            ],
            capture_output=True,
            text=True,
        )
        if cp.returncode != 0 or not wav_path.is_file():
            raise RuntimeError(f"vocal separation failed: {cp.stderr[-300:]}")
    else:
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
    samples = read_wav(wav_path)
    pipeline = speakrs.Pipeline.from_pretrained(args.mode)
    pipeline_config = make_config(speakrs, args.profile)
    turns: list[dict[str, object]] = []
    next_id = 1
    if float(args.chunk_sec) <= 0:
        result = pipeline.diarize_file(str(wav_path), pipeline_config=pipeline_config)
        segments = getattr(result, "exclusive_segments", None) or result.segments
        labels = local_labels(segments)
        mapping = {label: f"Speaker_{index + 1}" for index, label in enumerate(labels)}
        turns = [
            {
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "speaker": mapping[str(segment.speaker)],
            }
            for segment in segments
        ]
        payload = {"speaker_turns": turns, "speaker_embeddings": {}}
        Path(args.output).write_text(json.dumps(payload), encoding="utf-8")
        print(json.dumps({"turns": len(turns), "speakers": len(mapping)}))
        return 0
    chunk = max(30.0, float(args.chunk_sec))
    overlap_sec = max(0.0, min(float(args.overlap_sec), chunk - 1.0))
    start = 0.0
    total = len(samples) / 16000.0
    while start < total - 0.01:
        end = min(total, start + chunk)
        first = int(start * 16000)
        last = int(end * 16000)
        result = pipeline.diarize_samples(
            samples[first:last], file_id=f"chunk_{int(start)}", pipeline_config=pipeline_config
        )
        segments = getattr(result, "exclusive_segments", None) or result.segments
        labels = local_labels(segments)
        existing = [turn for turn in turns if float(turn["end"]) > start]
        mapping, next_id = assign_labels(labels, segments, start, existing, next_id)
        for segment in segments:
            turns.append(
                {
                    "start": round(start + float(segment.start), 3),
                    "end": round(start + float(segment.end), 3),
                    "speaker": mapping[str(segment.speaker)],
                }
            )
        if end >= total:
            break
        start = end - overlap_sec

    turns.sort(key=lambda item: float(item["start"]))
    payload = {"speaker_turns": turns, "speaker_embeddings": {}}
    Path(args.output).write_text(json.dumps(payload), encoding="utf-8")
    print(json.dumps({"turns": len(turns), "speakers": len({t["speaker"] for t in turns})}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
