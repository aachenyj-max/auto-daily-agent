#!/usr/bin/env python3
"""Small OpenAI-compatible LLM client with local-only config loading."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


@dataclass
class LLMConfig:
    api_key: str | None
    api_base: str | None
    model: str | None
    profile: str = "default"

    @property
    def ready(self) -> bool:
        return bool(self.api_key and self.api_base and self.model)

    def public_status(self) -> dict[str, Any]:
        return {
            "configured": self.ready,
            "has_api_key": bool(self.api_key),
            "api_base": self.api_base or "",
            "model": self.model or "",
            "profile": self.profile,
        }


def parse_scalar(value: str) -> str:
    return value.strip().strip('"').strip("'")


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned_key = key.strip().lstrip("\ufeff")
        values[cleaned_key] = parse_scalar(value)
    return values


def parse_minimal_yaml(text: str) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    current_section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            settings[current_section] = {}
            continue
        if current_section and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            settings.setdefault(current_section, {})[key.strip()] = parse_scalar(value)
    return settings


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml

        return yaml.safe_load(text) or {}
    except ImportError:
        return parse_minimal_yaml(text)


def load_llm_config(api_key: str | None = None, profile: str = "default") -> LLMConfig:
    settings = load_yaml_file(CONFIG_DIR / "settings.yaml")
    local_settings = load_yaml_file(CONFIG_DIR / "local.yaml")
    env_file = parse_env_file(PROJECT_ROOT / ".env.local")

    llm = settings.get("llm", {}) if isinstance(settings.get("llm"), dict) else {}
    local_llm = local_settings.get("llm", {}) if isinstance(local_settings.get("llm"), dict) else {}
    profile = profile or "default"
    prefix = f"{profile.upper()}_LLM"
    profile_llm = llm.get(profile, {}) if isinstance(llm.get(profile), dict) else {}
    local_profile_llm = local_llm.get(profile, {}) if isinstance(local_llm.get(profile), dict) else {}

    key = (
        api_key
        or os.getenv(f"{prefix}_API_KEY")
        or env_file.get(f"{prefix}_API_KEY")
        or local_profile_llm.get("api_key")
        or profile_llm.get("api_key")
        or os.getenv("LLM_API_KEY")
        or env_file.get("LLM_API_KEY")
        or local_llm.get("api_key")
        or llm.get("api_key")
    )
    api_base = (
        os.getenv(f"{prefix}_API_BASE")
        or env_file.get(f"{prefix}_API_BASE")
        or local_profile_llm.get("api_base")
        or profile_llm.get("api_base")
        or os.getenv("LLM_API_BASE")
        or env_file.get("LLM_API_BASE")
        or local_llm.get("api_base")
        or llm.get("api_base")
    )
    model = (
        os.getenv(f"{prefix}_MODEL")
        or env_file.get(f"{prefix}_MODEL")
        or local_profile_llm.get("model")
        or profile_llm.get("model")
        or os.getenv("LLM_MODEL")
        or env_file.get("LLM_MODEL")
        or local_llm.get("model")
        or llm.get("model")
    )
    return LLMConfig(
        api_key=str(key).strip() if key else None,
        api_base=str(api_base).strip() if api_base else None,
        model=str(model).strip() if model else None,
        profile=profile,
    )


def chat_completion(
    messages: list[dict[str, str]],
    api_key: str | None = None,
    profile: str = "default",
    temperature: float = 0.4,
    max_tokens: int = 4000,
    timeout: int = 120,
    retries: int = 2,
) -> str:
    config = load_llm_config(api_key, profile=profile)
    if not config.ready:
        missing = []
        if not config.api_key:
            missing.append(f"{profile.upper()}_LLM_API_KEY")
        if not config.api_base:
            missing.append(f"{profile.upper()}_LLM_API_BASE")
        if not config.model:
            missing.append(f"{profile.upper()}_LLM_MODEL")
        raise RuntimeError(f"LLM not configured: {', '.join(missing)}")

    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{config.api_base.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
            break
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"LLM HTTP {exc.code}: {detail[:500]}")
            if exc.code != 429 and exc.code < 500:
                raise last_error from exc
        except error.URLError as exc:
            last_error = RuntimeError(f"LLM request failed: {exc.reason}")
        if attempt >= retries:
            raise last_error
        time.sleep(1.5 * (attempt + 1))

    data = json.loads(raw)
    return data["choices"][0]["message"]["content"].strip()
