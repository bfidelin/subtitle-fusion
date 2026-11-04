from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torchaudio
from pyannote.audio import Inference, Model
from sklearn.cluster import AgglomerativeClustering


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--turns", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--max-clips", type=int, default=3)
    parser.add_argument("--constrained", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse()
    payload = json.loads(Path(args.turns).read_text(encoding="utf-8"))
    turns = payload["speaker_turns"]
    by_speaker = defaultdict(list)
    for turn in turns:
        by_speaker[str(turn["speaker"])].append(turn)

    waveform, sample_rate = torchaudio.load(args.audio)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    inference = Inference(model, window="whole", device=device)

    labels = sorted(by_speaker)
    embeddings = []
    for label in labels:
        clips = sorted(
            by_speaker[label],
            key=lambda turn: float(turn["end"]) - float(turn["start"]),
            reverse=True,
        )[: args.max_clips]
        vectors = []
        for turn in clips:
            start = int(float(turn["start"]) * sample_rate)
            end = min(waveform.shape[1], int(float(turn["end"]) * sample_rate))
            if end - start < sample_rate // 4:
                continue
            audio = waveform[:, start:end]
            vector = inference({"waveform": audio, "sample_rate": sample_rate})
            vector = np.asarray(vector, dtype=np.float32).reshape(-1)
            vectors.append(vector / (np.linalg.norm(vector) + 1e-8))
        if vectors:
            embeddings.append(np.mean(vectors, axis=0))
        else:
            embeddings.append(np.zeros(256, dtype=np.float32))
    matrix = np.stack(embeddings)
    matrix = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)
    windows = {
        label: {int(turn["window"]) for turn in by_speaker[label] if "window" in turn}
        for label in labels
    }
    if args.constrained and any(windows.values()):
        clusters = [
            {"members": [index], "windows": set(windows[label]), "vector": matrix[index]}
            for index, label in enumerate(labels)
        ]
        while len(clusters) > 1:
            best = None
            for left in range(len(clusters)):
                for right in range(left + 1, len(clusters)):
                    if clusters[left]["windows"] & clusters[right]["windows"]:
                        continue
                    similarity = float(np.dot(clusters[left]["vector"], clusters[right]["vector"]))
                    if similarity < args.threshold:
                        continue
                    if best is None or similarity > best[0]:
                        best = (similarity, left, right)
            if best is None:
                break
            _, left, right = best
            vector = clusters[left]["vector"] + clusters[right]["vector"]
            vector = vector / (np.linalg.norm(vector) + 1e-8)
            clusters[left] = {
                "members": clusters[left]["members"] + clusters[right]["members"],
                "windows": clusters[left]["windows"] | clusters[right]["windows"],
                "vector": vector,
            }
            clusters.pop(right)
        cluster_ids = [0] * len(labels)
        for cluster_index, cluster in enumerate(clusters):
            for member in cluster["members"]:
                cluster_ids[member] = cluster_index
        cluster_ids = np.asarray(cluster_ids)
    else:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1.0 - args.threshold,
            metric="cosine",
            linkage="average",
        )
        cluster_ids = clustering.fit_predict(matrix)
    label_to_speaker = {
        label: f"Speaker_{int(cluster) + 1}" for label, cluster in zip(labels, cluster_ids)
    }
    for turn in turns:
        turn["speaker"] = label_to_speaker[str(turn["speaker"])]
    Path(args.output).write_text(json.dumps(payload), encoding="utf-8")
    print(json.dumps({"input_speakers": len(labels), "output_speakers": len(set(cluster_ids))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
