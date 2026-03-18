from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Tuple

from openai import OpenAI


DEFAULT_OPENAI_MODEL = "gpt-5-mini"


@dataclass
class OpenAISettings:
    api_key: str = ""
    base_url: str | None = None
    model: str = DEFAULT_OPENAI_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


def _strip_shell_value(raw_value: str) -> str:
    value = raw_value.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    return value


def load_zsh_exports() -> Dict[str, str]:
    zshrc_path = Path.home() / ".zshrc"
    if not zshrc_path.exists():
        return {}

    exports: Dict[str, str] = {}
    text = zshrc_path.read_text(encoding="utf-8", errors="ignore")

    for line in text.splitlines():
        match = re.match(r"\s*export\s+(OPENAI_[A-Z0-9_]+)=(.+)\s*$", line)
        if not match:
            continue
        exports[match.group(1)] = _strip_shell_value(match.group(2))

    return exports


def load_openai_settings(preferred_model: str | None = None) -> OpenAISettings:
    zsh_exports = load_zsh_exports()
    api_key = os.getenv("OPENAI_API_KEY") or zsh_exports.get("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL") or zsh_exports.get("OPENAI_BASE_URL")
    model = (
        preferred_model
        or os.getenv("OPENAI_MODEL")
        or zsh_exports.get("OPENAI_MODEL")
        or DEFAULT_OPENAI_MODEL
    )
    return OpenAISettings(api_key=api_key, base_url=base_url, model=model)


def openai_available(preferred_model: str | None = None) -> bool:
    return load_openai_settings(preferred_model).enabled


def build_openai_agent(
    llm_enabled: bool, llm_model: str | None = None
) -> "OpenAIJSONAgent | None":
    if not llm_enabled:
        return None

    settings = load_openai_settings(llm_model)
    if not settings.enabled:
        return None
    return OpenAIJSONAgent(settings)


def _extract_json_content(raw_text: str) -> str:
    candidate = raw_text.strip()
    fenced_match = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```", candidate, flags=re.DOTALL
    )
    if fenced_match:
        return fenced_match.group(1)

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        return candidate[start : end + 1]
    return candidate


class OpenAIJSONAgent:
    def __init__(self, settings: OpenAISettings):
        self.settings = settings
        self.model = settings.model
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)

    def ask_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> Tuple[Dict[str, Any] | None, str | None]:
        try:
            request: Dict[str, Any] = {
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if not self.model.startswith("gpt-5"):
                request["temperature"] = temperature

            response = self.client.chat.completions.create(
                **request,
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(_extract_json_content(content))
            if not isinstance(payload, dict):
                return None, "OpenAI 返回内容不是 JSON 对象。"
            return payload, None
        except (
            Exception
        ) as exc:  # pragma: no cover - network failures are runtime concerns
            return None, str(exc)
