"""The model gateway: the single seam every chat completion and embedding goes through."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

Message = Mapping[str, str]
"""A chat message: ``{"role": "system" | "user" | "assistant", "content": "..."}``."""


@dataclass(frozen=True)
class ChatResult:
    text: str
    input_tokens: int
    output_tokens: int


class ModelGateway(Protocol):
    def chat(self, model: str, messages: Sequence[Message]) -> ChatResult:
        """Return one chat completion for ``messages``."""
        ...

    def embed(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding per text, in order."""
        ...


class ScriptedGateway:
    """Fake gateway for tests: chat replies and embeddings are set per test.

    ``chat_replies`` are returned in order, one per chat call. ``embeddings`` maps a
    keyword to a vector: a text gets the vector of the first keyword it contains
    (case-insensitive), or ``default_embedding`` if it contains none.
    """

    def __init__(
        self,
        chat_replies: Sequence[str] = (),
        embeddings: Mapping[str, Sequence[float]] | None = None,
        default_embedding: Sequence[float] | None = None,
    ) -> None:
        self._chat_replies = list(chat_replies)
        self._embeddings = dict(embeddings or {})
        self._default_embedding = default_embedding

    def chat(self, model: str, messages: Sequence[Message]) -> ChatResult:
        if not self._chat_replies:
            raise AssertionError("ScriptedGateway got a chat call but has no scripted reply left")
        text = self._chat_replies.pop(0)
        prompt_words = sum(len(m["content"].split()) for m in messages)
        return ChatResult(text=text, input_tokens=prompt_words, output_tokens=len(text.split()))

    def embed(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        lowered = text.lower()
        for keyword, vector in self._embeddings.items():
            if keyword.lower() in lowered:
                return list(vector)
        if self._default_embedding is None:
            raise AssertionError(f"ScriptedGateway has no embedding scripted for: {text!r}")
        return list(self._default_embedding)
