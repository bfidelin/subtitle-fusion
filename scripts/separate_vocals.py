from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import torch
import torchaudio


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chunk-sec", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse()
    work = Path("/home/calmos/tmp/speakrs")
    work.mkdir(parents=True, exist_ok=True)
    source = work / "separator_input.wav"
    cp = subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y", "-i", args.audio,
            "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(source),
        ],
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0 or not source.is_file():
        raise RuntimeError(f"ffmpeg extraction failed: {cp.stderr[-300:]}")

    model = torchaudio.pipelines.HDEMUCS_HIGH_MUSDB_PLUS.get_model()
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    waveform, sample_rate = torchaudio.load(str(source))
    if waveform.shape[0] == 1:
        waveform = waveform.repeat(2, 1)
    waveform = waveform.to(device)
    chunk = max(5.0, float(args.chunk_sec)) * sample_rate
    pieces = []
    with torch.inference_mode():
        for start in range(0, waveform.shape[1], int(chunk)):
            piece = waveform[:, start : start + int(chunk)]
            if piece.shape[1] < 512:
                continue
            separated = model(piece.unsqueeze(0))[0]
            vocals = separated[3].mean(dim=0, keepdim=True)
            pieces.append(vocals.cpu())
    vocals = torch.cat(pieces, dim=1).clamp(-1, 1)
    vocals = torchaudio.functional.resample(vocals, sample_rate, 16000)
    torchaudio.save(args.output, vocals, 16000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
