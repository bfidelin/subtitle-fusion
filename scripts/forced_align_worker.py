from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import torch
import torchaudio


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", required=True)
    parser.add_argument("--segments", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", default="en")
    return parser.parse_args()


def load_audio(path: str) -> tuple[torch.Tensor, int]:
    wav_dir = Path("/home/calmos/tmp/forced-align")
    wav_dir.mkdir(parents=True, exist_ok=True)
    wav_path = wav_dir / "input.wav"
    cp = subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y", "-i", path,
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path),
        ],
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0 or not wav_path.is_file():
        raise RuntimeError(f"ffmpeg extraction failed: {cp.stderr[-300:]}")
    waveform, sample_rate = torchaudio.load(str(wav_path))
    return waveform.mean(dim=0, keepdim=True), sample_rate


def clean_tokens(text: str, labels: dict[str, int]) -> list[int]:
    tokens: list[int] = []
    for char in text.upper():
        if char in labels:
            tokens.append(labels[char])
    return tokens


def align_segment(
    waveform: torch.Tensor,
    sample_rate: int,
    segment: dict,
    model,
    labels: dict[str, int],
    blank: int,
) -> list[dict]:
    start = float(segment.get("start", 0.0))
    end = float(segment.get("end", start))
    words = list(segment.get("words") or [])
    if not words or end <= start:
        return words
    first = max(0, int(start * sample_rate))
    last = min(waveform.shape[1], int(end * sample_rate))
    if last <= first:
        return words
    audio = waveform[:, first:last]
    if audio.shape[1] < 512:
        return words
    with torch.inference_mode():
        emissions = model(audio)[0]
    log_probs = torch.log_softmax(emissions, dim=-1)

    targets: list[int] = []
    token_word: list[int] = []
    for word_index, word in enumerate(words):
        tokens = clean_tokens(str(word.get("text", "")), labels)
        if word_index and targets:
            targets.append(labels["|"])
            token_word.append(max(0, word_index - 1))
        for token in tokens:
            targets.append(token)
            token_word.append(word_index)
    if not targets:
        return words
    if len(targets) >= emissions.shape[1]:
        return words

    alignment, scores = torchaudio.functional.forced_align(
        log_probs, torch.tensor([targets], device=log_probs.device), blank=blank
    )
    path = alignment[0].tolist()
    runs: list[list[int]] = []
    for frame, value in enumerate(path):
        if runs and runs[-1][0] == value:
            runs[-1][2] = frame
        else:
            runs.append([value, frame, frame])
    runs = [run for run in runs if run[0] != blank]

    token_index = 0
    spans: dict[int, list[float]] = {}
    for value, frame_start, frame_end in runs:
        while token_index < len(targets) and targets[token_index] != value:
            token_index += 1
        if token_index >= len(targets):
            break
        word_index = token_word[token_index]
        token_start = frame_start * (end - start) / max(1, emissions.shape[1]) + start
        token_end = (frame_end + 1) * (end - start) / max(1, emissions.shape[1]) + start
        if word_index in spans:
            spans[word_index][1] = max(spans[word_index][1], token_end)
        else:
            spans[word_index] = [token_start, token_end]
        token_index += 1

    for word_index, word in enumerate(words):
        if word_index not in spans:
            continue
        word["start"] = round(spans[word_index][0], 3)
        word["end"] = round(spans[word_index][1], 3)
        word["alignment"] = "wav2vec2"
    return words


def main() -> int:
    args = parse()
    if args.language not in {"en", "eng", None}:
        return 0
    labels = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H.get_labels()
    char_to_index = {label: index for index, label in enumerate(labels) if label != "-"}
    blank = 0
    model = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H.get_model()
    model.eval()
    if torch.cuda.is_available():
        model.to("cuda")

    waveform, sample_rate = load_audio(args.media)
    if torch.cuda.is_available():
        waveform = waveform.to("cuda")
    payload = json.loads(Path(args.segments).read_text(encoding="utf-8"))
    for segment in payload:
        words = segment.get("words") or []
        if not words:
            continue
        segment["words"] = align_segment(
            waveform, sample_rate, segment, model, char_to_index, blank
        )
    Path(args.output).write_text(json.dumps(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
