"""Providers that speak the OpenAI chat-completions protocol.

DeepSeek, OpenAI, Together, Groq, OpenRouter and most hosted inference services
expose the same `/chat/completions` shape, so one implementation covers all of
them and each concrete provider is just a base URL, a key and default models.

**When to use one of these instead of Ollama:** local models are free and
private, and everything in this app is built to work with them. Where a hosted
model earns its cost is *feedback quality* — a small local model reliably finds
that something is wrong but is vague about exactly which words, and tends to
collapse every category into "grammar". Since the mistake bank keys on the
corrected pair, that vagueness is the difference between tracking "discussed
about → discussed" and tracking a whole sentence.

Cost for a single learner is small: a day of lessons, feedback and conversation
is a few thousand tokens. Check current pricing before committing to a provider.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .base import TIER_MEDIUM, AIProvider, AIResult, AIUnavailable


class OpenAICompatibleProvider(AIProvider):
    """Base for any hosted service using the OpenAI chat-completions API."""

    name = "openai-compatible"
    base_url = ""
    default_models: dict[str, str] = {}
    api_key_setting = ""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        models: dict | None = None,
    ):
        from django.conf import settings

        conf = settings.AI
        self.api_key = api_key or conf.get(self.api_key_setting, "")
        self.base_url = (base_url or conf.get(f"{self.name.upper()}_BASE_URL") or self.base_url).rstrip("/")
        self.timeout = timeout or conf.get("REMOTE_TIMEOUT", 90)
        configured = models or conf.get(f"{self.name.upper()}_MODELS") or {}
        self.models = {**self.default_models, **{k: v for k, v in configured.items() if v}}

    def model_for(self, tier: str) -> str:
        chain = {
            "large": ["large", "medium", "small"],
            "medium": ["medium", "small", "large"],
            "small": ["small", "medium"],
        }
        for candidate in chain.get(tier, ["medium"]):
            model = self.models.get(candidate)
            if model:
                return model
        raise AIUnavailable(f"No model configured for {self.name}.")

    def _post(self, payload: dict) -> dict:
        if not self.api_key:
            raise AIUnavailable(
                f"No API key for {self.name}. Set {self.api_key_setting} in your .env file, "
                "or switch AI_PROVIDER back to ollama."
            )
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise AIUnavailable(f"{self.name} took longer than {self.timeout}s to respond.") from exc
        except requests.ConnectionError as exc:
            raise AIUnavailable(f"Cannot reach {self.name} at {self.base_url}.") from exc
        except requests.HTTPError as exc:
            status = response.status_code
            detail = ""
            try:
                detail = response.json().get("error", {}).get("message", "")
            except Exception:  # noqa: BLE001 - error bodies are not always JSON
                detail = response.text[:200]
            if status in (401, 403):
                raise AIUnavailable(
                    f"{self.name} rejected the API key. Check {self.api_key_setting}."
                ) from exc
            if status == 429:
                raise AIUnavailable(
                    f"{self.name} is rate limiting or out of credit. {detail}"
                ) from exc
            raise AIUnavailable(f"{self.name} request failed ({status}): {detail}") from exc

    def _complete(self, messages: list[dict], *, tier: str, temperature: float,
                  json_mode: bool = False, max_tokens: int | None = None) -> AIResult:
        model = self.model_for(tier)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        started = time.perf_counter()
        data = self._post(payload)
        duration_ms = int((time.perf_counter() - started) * 1000)

        choices = data.get("choices") or []
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage") or {}
        return AIResult(
            text=text,
            model=model,
            tier=tier,
            duration_ms=duration_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            meta={"cached_tokens": usage.get("prompt_cache_hit_tokens")},
        )

    def generate(self, prompt, *, system=None, tier=TIER_MEDIUM, temperature=0.7,
                 json_mode=False, max_tokens=None) -> AIResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        # These APIs require the word "json" in the prompt when JSON mode is on.
        if json_mode and "json" not in prompt.lower():
            prompt = f"{prompt}\n\nReply with JSON only."
        messages.append({"role": "user", "content": prompt})
        return self._complete(
            messages, tier=tier, temperature=temperature, json_mode=json_mode, max_tokens=max_tokens
        )

    def chat(self, messages, *, tier=TIER_MEDIUM, temperature=0.8) -> AIResult:
        return self._complete(messages, tier=tier, temperature=temperature)

    def health(self) -> dict:
        info = {"provider": self.name, "base_url": self.base_url, "models": {
            tier: {"configured": model, "installed": True} for tier, model in self.models.items()
        }}
        if not self.api_key:
            return {
                **info,
                "reachable": False,
                "error": "No API key configured.",
                "setup_hint": (
                    f"Add {self.api_key_setting}=your-key to .env and set "
                    f"AI_PROVIDER={self.name}, then restart the server."
                ),
            }
        try:
            # One-token round trip: cheapest honest way to prove the key works.
            self._complete(
                [{"role": "user", "content": "ping"}],
                tier="small",
                temperature=0,
                max_tokens=1,
            )
        except AIUnavailable as exc:
            return {**info, "reachable": False, "error": str(exc), "setup_hint": str(exc)}
        return {**info, "reachable": True, "setup_hint": ""}


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek: cheap, and strong at the structured-feedback work this app
    leans on.

    Model names verified against api-docs.deepseek.com in September 2026. The
    older `deepseek-chat` and `deepseek-reasoner` aliases were retired on
    2026-07-24 and are no longer routed, so anything still using them fails
    outright rather than degrading.

    Tiering reflects cost, not capability worship: Flash handles vocabulary
    extraction, lessons and conversation perfectly well and is roughly a third
    of the price. Pro is reserved for the large tier, which is where detailed
    writing and conversation review live -- the one place where being vague
    about *which words* were wrong actually costs the learner something.
    """

    name = "deepseek"
    base_url = "https://api.deepseek.com"
    api_key_setting = "DEEPSEEK_API_KEY"
    default_models = {
        "small": "deepseek-v4-flash",
        "medium": "deepseek-v4-flash",
        "large": "deepseek-v4-pro",
    }


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1"
    api_key_setting = "OPENAI_API_KEY"
    default_models = {
        "small": "gpt-4o-mini",
        "medium": "gpt-4o-mini",
        "large": "gpt-4o",
    }
