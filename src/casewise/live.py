"""The real gateway: a configured chat provider plus Sentence Transformers embeddings.

Provider SDKs and model weights are imported and loaded on first use, so building a
gateway is free and tests never pay for them. Install them with ``uv sync --extra live``.
"""

from __future__ import annotations

import importlib
import os
import time
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


GROQ_RETRIES = 8
"""Retries the Groq SDK makes after a rate-limit or server error before giving up."""


GROQ_TIMEOUT_S = 120.0
"""How long one Groq request may take before it is abandoned and retried."""


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
    # The SDK retries rate limits (429) and server errors itself, with backoff that
    # honors Retry-After. A free-tier evaluation run hits the per-minute limits often.
    # The timeout bounds each attempt, so a stalled connection fails and is retried.
    client = Groq(max_retries=GROQ_RETRIES, timeout=GROQ_TIMEOUT_S)  # reads GROQ_API_KEY

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


GEMINI_RETRIES = 5
"""Retries after a rate-limit, overload or connection error, waiting 5, 10, 20, 40 then
60 seconds."""

GEMINI_TIMEOUT_MS = 120_000
"""How long one Gemini request may take before it is abandoned and retried."""


def _gemini_chat() -> ChatFn:
    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as error:
        raise _missing("google-genai") from error
    # google-genai sends requests through httpx2 (3.x) or httpx (older). Both may be
    # installed, so retry either library's transport errors.
    transport_errors: tuple[type[Exception], ...] = ()
    for module in ("httpx2", "httpx"):
        try:
            transport_errors += (importlib.import_module(module).TransportError,)
        except ImportError:
            pass

    if not os.environ.get("GEMINI_API_KEY"):
        raise LiveUnavailable(
            "Live chat calls to Gemini need GEMINI_API_KEY (from Google AI Studio). Export "
            "it or put it in a .env file in the directory you run casewise from."
        )
    # With no timeout, one stalled connection once hung an evaluation run for a day.
    client = genai.Client(  # reads GEMINI_API_KEY
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS)
    )

    def chat(model: str, messages: Sequence[Message]) -> ChatResult:
        # Gemini takes system text separately and calls the assistant role "model".
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
            if m["role"] != "system"
        ]
        config = types.GenerateContentConfig(system_instruction=system or None, temperature=0)
        for attempt in range(GEMINI_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=model, contents=contents, config=config
                )
                break
            except (errors.APIError, *transport_errors) as error:
                # Free-tier rate limits (429), overload (503), timeouts and dropped
                # connections clear if you wait.
                transient = isinstance(error, transport_errors) or error.code in (429, 500, 503)
                if not transient or attempt == GEMINI_RETRIES:
                    raise
                time.sleep(min(60, 5 * 2**attempt))
        usage = response.usage_metadata
        return ChatResult(
            text=response.text or "",
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
        )

    return chat


CHAT_PROVIDERS: dict[str, Callable[[], ChatFn]] = {"groq": _groq_chat, "gemini": _gemini_chat}
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


def build_gateway(settings: Settings, *, provider: str | None = None) -> ModelGateway:
    """Build the gateway the configuration asks for (see ``Settings.gateway_mode``).

    ``provider`` overrides ``settings.provider``: the evaluation judge passes
    ``settings.judge_provider``.
    """
    provider = provider or settings.provider
    if settings.gateway_mode == "replay":
        return CachedGateway(settings.cache_dir)
    if settings.gateway_mode == "record":
        return CachedGateway(settings.cache_dir, provider=LiveGateway(provider))
    if settings.gateway_mode == "live":
        return LiveGateway(provider)
    raise ValueError(
        f"Unknown gateway mode {settings.gateway_mode!r}. Use one of: live, record, replay"
    )
