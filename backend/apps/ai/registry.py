"""Provider registry and the single entry point the rest of the app uses."""
from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from .providers.base import AIProvider
from .providers.ollama import OllamaProvider

# Future providers register here. Nothing else in the codebase needs to change.
PROVIDERS: dict[str, type[AIProvider]] = {
    "ollama": OllamaProvider,
}


@lru_cache(maxsize=None)
def get_ai_provider(name: str | None = None) -> AIProvider:
    """Return the configured provider. Cached: providers are stateless."""
    key = (name or settings.AI["PROVIDER"]).lower()
    try:
        return PROVIDERS[key]()
    except KeyError as exc:
        available = ", ".join(sorted(PROVIDERS))
        raise ValueError(
            f"Unknown AI_PROVIDER {key!r}. Available providers: {available}."
        ) from exc
