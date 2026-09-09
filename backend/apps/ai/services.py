"""Thin service wrapper adding caching and logging around the AI provider."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable

from .models import AICache, AIRequestLog
from .providers.base import AIError
from .registry import get_ai_provider

logger = logging.getLogger(__name__)


def cache_key(task: str, model: str, payload: dict[str, Any]) -> str:
    blob = json.dumps({"task": task, "model": model, "payload": payload}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cached(task: str, inputs: dict[str, Any], producer: Callable[[], Any], *, model: str = "") -> Any:
    """Run `producer` unless an identical request was already answered.

    Cache misses are the only path that costs compute, so every expensive
    generation in the app should go through here.
    """
    key = cache_key(task, model, inputs)
    entry = AICache.objects.filter(key=key).first()
    if entry:
        AICache.objects.filter(pk=entry.pk).update(hits=entry.hits + 1)
        return entry.payload

    value = producer()
    AICache.objects.update_or_create(
        key=key, defaults={"task": task, "model": model, "payload": value}
    )
    return value


def log_call(task: str, user=None, *, store_prompt: str = "") -> Callable:
    """Decorator-free helper: wrap a provider call and record the outcome."""

    def runner(fn: Callable[[], Any]):
        provider = get_ai_provider()
        try:
            result = fn()
            AIRequestLog.objects.create(
                user=user,
                provider=provider.name,
                model=getattr(result, "model", ""),
                tier=getattr(result, "tier", ""),
                task=task,
                duration_ms=getattr(result, "duration_ms", 0),
                prompt_tokens=getattr(result, "prompt_tokens", None),
                completion_tokens=getattr(result, "completion_tokens", None),
                success=True,
                prompt=store_prompt,
            )
            return result
        except AIError as exc:
            AIRequestLog.objects.create(
                user=user,
                provider=provider.name,
                model="",
                tier="",
                task=task,
                success=False,
                error=str(exc),
                prompt=store_prompt,
            )
            logger.warning("AI task %s failed: %s", task, exc)
            raise

    return runner


def ai_health() -> dict[str, Any]:
    return get_ai_provider().health()
