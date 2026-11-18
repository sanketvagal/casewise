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

    ``chat_replies`` is either a sequence, returned in order one per chat call, or a
    mapping from a step's output type (``intent``, ``grounding``, ``draft``,
    ``review_draft``: the ``Output:`` a structured prompt asks for) to what the model
    says at that step. A string answers every call to its step; a sequence answers
    successive calls, retries included, in order.

    ``embeddings`` maps a keyword to a vector: a text gets the vector of the first
    keyword it contains (case-insensitive), or ``default_embedding`` if it contains none.
    """

    def __init__(
        self,
        chat_replies: Sequence[str] | Mapping[str, str | Sequence[str]] = (),
        embeddings: Mapping[str, Sequence[float]] | None = None,
        default_embedding: Sequence[float] | None = None,
    ) -> None:
        if isinstance(chat_replies, Mapping):
            self._replies_by_step = {
                step: reply if isinstance(reply, str) else list(reply)
                for step, reply in chat_replies.items()
            }
            self._chat_replies: list[str] | None = None
        else:
            self._replies_by_step = None
            self._chat_replies = list(chat_replies)
        self._embeddings = dict(embeddings or {})
        self._default_embedding = default_embedding

    def chat(self, model: str, messages: Sequence[Message]) -> ChatResult:
        text = self._next_reply(messages)
        prompt_words = sum(len(m["content"].split()) for m in messages)
        return ChatResult(text=text, input_tokens=prompt_words, output_tokens=len(text.split()))

    def embed(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _next_reply(self, messages: Sequence[Message]) -> str:
        if self._chat_replies is not None:
            if not self._chat_replies:
                raise AssertionError(
                    "ScriptedGateway got a chat call but has no scripted reply left"
                )
            return self._chat_replies.pop(0)
        from casewise.structured import requested_output

        step = requested_output(messages)
        reply = self._replies_by_step.get(step) if step else None
        if reply is None:
            raise AssertionError(f"ScriptedGateway has no reply scripted for step {step!r}")
        if isinstance(reply, str):
            return reply
        if not reply:
            raise AssertionError(f"ScriptedGateway has no {step!r} reply left")
        return reply.pop(0)

    def _embed_one(self, text: str) -> list[float]:
        lowered = text.lower()
        for keyword, vector in self._embeddings.items():
            if keyword.lower() in lowered:
                return list(vector)
        if self._default_embedding is None:
            raise AssertionError(f"ScriptedGateway has no embedding scripted for: {text!r}")
        return list(self._default_embedding)
