"""Ollama provider: the default, zero-recurring-cost backend."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings

from .base import TIER_MEDIUM, AIProvider, AIResult, AIUnavailable

logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, timeout: int | None = None, models: dict | None = None):
        conf = settings.AI
        self.base_url = (base_url or conf["OLLAMA_BASE_URL"]).rstrip("/")
        self.timeout = timeout or conf["OLLAMA_TIMEOUT"]
        self.models = models or conf["MODELS"]

    # -- helpers ------------------------------------------------------------
    def model_for(self, tier: str) -> str:
        """Resolve a tier to a model name, falling back down the tiers.

        A missing LARGE model must not break the feature that asked for it, so
        large falls back to medium and medium to small.
        """
        chain = {"large": ["large", "medium", "small"], "medium": ["medium", "small"], "small": ["small"]}
        for candidate in chain.get(tier, ["medium", "small"]):
            model = self.models.get(candidate)
            if model:
                return model
        raise AIUnavailable("No AI model is configured. Set AI_MODEL_SMALL in your .env file.")

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}/api/{endpoint}"
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise AIUnavailable(
                f"The local model took longer than {self.timeout}s to respond."
            ) from exc
        except requests.ConnectionError as exc:
            raise AIUnavailable(
                f"Cannot reach Ollama at {self.base_url}. Is it running? Try: ollama serve"
            ) from exc
        except requests.HTTPError as exc:
            detail = ""
            try:
                detail = response.json().get("error", "")
            except Exception:  # noqa: BLE001 - response body may not be JSON
                detail = response.text[:200]
            if "not found" in detail.lower():
                raise AIUnavailable(
                    f"Model not installed. Run: ollama pull {payload.get('model')}"
                ) from exc
            raise AIUnavailable(f"Ollama request failed: {detail or exc}") from exc

    # -- primitives ---------------------------------------------------------
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tier: str = TIER_MEDIUM,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> AIResult:
        model = self.model_for(tier)
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        started = time.perf_counter()
        data = self._post("generate", payload)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return self._log(AIResult(
            text=data.get("response", ""),
            model=model,
            tier=tier,
            duration_ms=duration_ms,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        ))

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: str = TIER_MEDIUM,
        temperature: float = 0.8,
    ) -> AIResult:
        model = self.model_for(tier)
        started = time.perf_counter()
        data = self._post(
            "chat",
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return self._log(AIResult(
            text=data.get("message", {}).get("content", ""),
            model=model,
            tier=tier,
            duration_ms=duration_ms,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        ), task="chat")

    def health(self) -> dict[str, Any]:
        """Report reachability and per-tier model availability with setup hints."""
        info: dict[str, Any] = {"provider": self.name, "base_url": self.base_url}
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            installed = [m["name"] for m in response.json().get("models", [])]
        except requests.RequestException as exc:
            return {
                **info,
                "reachable": False,
                "error": str(exc),
                "setup_hint": (
                    "Ollama is not responding. Install it from https://ollama.com, then run "
                    "'ollama serve' and pull a model, e.g. 'ollama pull qwen2.5:3b-instruct-q4_K_M'."
                ),
                "models": {},
            }

        models: dict[str, Any] = {}
        missing: list[str] = []
        for tier, configured in self.models.items():
            if not configured:
                models[tier] = {"configured": None, "installed": False}
                continue
            # Ollama reports "name:tag"; accept an exact match or a bare-name match.
            available = configured in installed or any(
                m.split(":")[0] == configured.split(":")[0] for m in installed
            )
            models[tier] = {"configured": configured, "installed": available}
            if not available:
                missing.append(configured)

        return {
            **info,
            "reachable": True,
            "installed_models": installed,
            "models": models,
            "setup_hint": (
                "Missing models. Run: " + " && ".join(f"ollama pull {m}" for m in missing)
                if missing
                else ""
            ),
        }
