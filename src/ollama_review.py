from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


def _load_first(env_name: str, dotenv_keys: tuple[str, ...] = ("OLLAMA_API_KEY",)) -> str | None:
    val = os.environ.get(env_name)
    if val:
        return val
    for dotenv in ("/home/calmos/.env", "/home/calmos/subtitle-fusion/.env"):
        try:
            for line in Path(dotenv).read_text().splitlines():
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() in dotenv_keys and not os.environ.get(env_name):
                        value = value.strip().strip('"').strip("'")
                        if value:
                            os.environ[env_name] = value
                            return value
        except OSError:
            continue
    return os.environ.get(env_name)


@dataclass(slots=True)
class OllamaReviewConfig:
    base_url: str = "https://ollama.com"
    model: str = "beam"
    api_key_env: str = "OLLAMA_API_KEY"
    timeout_sec: float = 30.0
    enabled: bool = False
    min_text_length: int = 4

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "OllamaReviewConfig":
        data = data or {}
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


def _normalize_url(base_url: str) -> str:
    return base_url.rstrip("/")


def review_text(
    raw_text: str,
    candidates: list[str],
    context: list[str],
    config: OllamaReviewConfig,
) -> tuple[str, bool, str]:
    if not config.enabled:
        return "", False, "disabled"
    if len(raw_text.strip()) < config.min_text_length:
        return "", False, "short"
    api_key = _load_first(config.api_key_env)
    if not api_key:
        return "", False, "missing_api_key"

    prompt = {
        "raw_text": raw_text.strip(),
        "candidate_names": candidates,
        "nearby_context": [item.strip() for item in context if item.strip()],
        "constraints": [
            "Preserve meaning.",
            "Fix spelling, grammar and punctuation only.",
            "Use candidate names only if supported by nearby context or OCR.",
            "Do not invent facts.",
            "Return JSON with keys changed (boolean), final (string), reason (string).",
        ],
    }
    url = f"{_normalize_url(config.base_url)}/api/chat"
    request_body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "You are a conservative subtitle editor. Output only JSON."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return "", False, f"request_failed:{type(exc).__name__}"

    message = payload.get("message", {}) if isinstance(payload, Mapping) else {}
    content = str(message.get("content", "")) if isinstance(message, Mapping) else ""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip().strip("`").strip()
        if content.startswith("json"):
            content = content[4:].strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        return "", False, "invalid_json"

    if not isinstance(result, Mapping):
        return "", False, "invalid_result"
    changed = result.get("changed") is True
    final = str(result.get("final", "")).strip()
    reason = str(result.get("reason", "")).strip()
    if not changed or not final:
        return "", False, reason or "no_change"
    raw = raw_text.strip()
    if len(final) < 0.5 * len(raw) or len(final) > 1.35 * len(raw):
        return "", False, "length_changed"
    return final, True, reason
