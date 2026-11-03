from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import cv2

from src.models import OCRHit


@dataclass(slots=True)
class FastOcrConfig:
    stride_sec: float = 5.0
    max_frames: int = 60
    min_confidence: float = 0.75
    min_text_length: int = 3
    max_text_length: int = 80
    scale: float = 1.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "FastOcrConfig":
        data = data or {}
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


class FastOcrUnavailableError(RuntimeError):
    """Raised when the fast OCR backend cannot be imported."""


def _rapid_engine() -> Any:
    try:
        from rapidocr import RapidOCR
    except Exception as exc:  # pragma: no cover - optional dependency
        raise FastOcrUnavailableError(str(exc)) from exc
    return RapidOCR()


def collect_sparse_ocr(media_path: Path, config: FastOcrConfig | None = None) -> list[OCRHit]:
    """Sample media sparsely and run fast PP-OCRv6-small OCR.

    This intentionally avoids 2.7s/frame PaddleOCR preprocessing. Typical speed is
    about 0.36s/frame on full frames, so a 5-second stride yields roughly 2-3s
    of OCR per minute of video without further losses.
    """
    config = config or FastOcrConfig()
    media_path = Path(media_path)
    if not media_path.is_file():
        raise FileNotFoundError(f"media file not found: {media_path}")

    engine = _rapid_engine()
    cap = cv2.VideoCapture(str(media_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open media: {media_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    if fps <= 0:
        fps = 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = (total_frames / fps) if total_frames > 0 else 0.0
    if duration <= 0:
        duration = 1e9

    hits: list[OCRHit] = []
    seen: set[str] = set()
    t = 0.0
    count = 0

    while t < duration and count < config.max_frames:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            t += config.stride_sec
            count += 1
            continue

        infer_frame = frame
        if float(config.scale) != 1.0:
            infer_frame = cv2.resize(frame, None, fx=config.scale, fy=config.scale, interpolation=cv2.INTER_CUBIC)

        try:
            output = engine(infer_frame)
        except Exception:
            t += config.stride_sec
            count += 1
            continue
        if not output or getattr(output, "boxes", None) is None:
            t += config.stride_sec
            count += 1
            continue

        for box, text, score in zip(getattr(output, "boxes", []), getattr(output, "txts", []), getattr(output, "scores", [])):
            clean = " ".join(str(text).split()).strip()
            if len(clean) < config.min_text_length or len(clean) > config.max_text_length:
                continue
            confidence = float(score)
            if confidence < config.min_confidence:
                continue
            key = (round(config.scale, 3), clean)
            if key in seen:
                continue
            seen.add(key)

            arr = [tuple(point) for point in box]
            x_min = int(min(p[0] for p in arr) / config.scale)
            y_min = int(min(p[1] for p in arr) / config.scale)
            x_max = int(max(p[0] for p in arr) / config.scale)
            y_max = int(max(p[1] for p in arr) / config.scale)
            hits.append(
                OCRHit(
                    text=clean,
                    time=float(t),
                    confidence=confidence,
                    bbox=(x_min, y_min, x_max - x_min, y_max - y_min),
                )
            )

        t += config.stride_sec
        count += 1

    cap.release()
    return hits
