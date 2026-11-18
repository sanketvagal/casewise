"""The real gateway: a configured chat provider plus Sentence Transformers embeddings.

Provider SDKs and model weights are imported and loaded on first use, so building a
gateway is free and tests never pay for them. Install them with ``uv sync --extra live``.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from typing import Any

from casewise.cache import CachedGateway
from casewise.config import Settings
from casewise.gateway import ChatResult, Message, ModelGateway


class LiveUnavailable(RuntimeError):
    """A live provider cannot be used: its package or its API key is missing."""


def _missing(package: str) -> LiveUnavailable:
    return LiveUnavailable(
        f"Live model calls need the '{package}' package. Install the live providers with "
        "`uv sync --extra live`, or set CASEWISE_GATEWAY_MODE=replay to use the cache only."
    )


ChatFn = Callable[[str, Sequence[Message]], ChatResult]

GROQ_REASONING_EFFORT = "medium"
"""Reasoning effort for Groq reasoning models (gpt-oss accepts low, medium or high).
Fixed in code and not part of the cache key (ADR 2): changing it means clearing the
cache by hand. "medium" is Groq's documented default, pinned so a change of default on
Groq's side cannot silently change recorded behavior."""


def _groq_chat() -> ChatFn:
    try:
        from groq import Groq
    except ImportError as error:
        raise _missing("groq") from error

    if not os.environ.get("GROQ_API_KEY"):
        raise LiveUnavailable(
            "Live chat calls to Groq need GROQ_API_KEY. Export it or put it in a .env file "
            "in the directory you run casewise from."
        )
    client = Groq()  # reads GROQ_API_KEY

    def chat(model: str, messages: Sequence[Message]) -> ChatResult:
        response = client.chat.completions.create(
            model=model,
            messages=[dict(m) for m in messages],
            temperature=0,
            # The answer is in message.content either way; this keeps the reasoning
            # text out of the response. gpt-oss rejects reasoning_format, so it is unset.
            reasoning_effort=GROQ_REASONING_EFFORT,
            include_reasoning=False,
        )
        return ChatResult(
            text=response.choices[0].message.content or "",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    return chat


CHAT_PROVIDERS: dict[str, Callable[[], ChatFn]] = {"groq": _groq_chat}
"""Chat providers by configuration name. Each factory builds its client when first called."""


class LiveGateway:
    def __init__(self, provider: str) -> None:
        if provider not in CHAT_PROVIDERS:
            known = ", ".join(sorted(CHAT_PROVIDERS))
            raise ValueError(f"Unknown provider {provider!r}. Known providers: {known}")
        self._provider = provider
        self._chat: ChatFn | None = None
        self._embedders: dict[str, Any] = {}

    def chat(self, model: str, messages: Sequence[Message]) -> ChatResult:
        if self._chat is None:
            self._chat = CHAT_PROVIDERS[self._provider]()
        return self._chat(model, messages)

    def embed(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        if model not in self._embedders:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise _missing("sentence-transformers") from error

            self._embedders[model] = SentenceTransformer(model)
        return self._embedders[model].encode(list(texts), normalize_embeddings=True).tolist()


def build_gateway(settings: Settings) -> ModelGateway:
    """Build the gateway the configuration asks for (see ``Settings.gateway_mode``)."""
    if settings.gateway_mode == "replay":
        return CachedGateway(settings.cache_dir)
    if settings.gateway_mode == "record":
        return CachedGateway(settings.cache_dir, provider=LiveGateway(settings.provider))
    if settings.gateway_mode == "live":
        return LiveGateway(settings.provider)
    raise ValueError(
        f"Unknown gateway mode {settings.gateway_mode!r}. Use one of: live, record, replay"
    )
