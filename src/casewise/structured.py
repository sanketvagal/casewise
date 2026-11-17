"""Structured output over a plain-text gateway: ask for JSON, parse it, validate it.

The gateway returns text (ADR 1), so every model step asks for a JSON object matching
a Pydantic model, parses the reply and validates it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from casewise.gateway import Message, ModelGateway

_OUTPUT_LINE = re.compile(r"^Output: (\w+)\.$", re.MULTILINE)


def output_instructions(output: type[BaseModel]) -> str:
    """The instructions appended to a step's system prompt, naming its output type."""
    schema = json.dumps(output.model_json_schema(), sort_keys=True)
    return (
        "Reply with only a JSON object and no other text.\n"
        f"Output: {_title(output)}.\n"
        f"The JSON object must match this JSON schema:\n{schema}"
    )


def requested_output(messages: Sequence[Message]) -> str | None:
    """The output type a prompt built with :func:`output_instructions` asks for."""
    for message in messages:
        found = _OUTPUT_LINE.search(message["content"])
        if found:
            return found.group(1)
    return None


@dataclass
class StructuredReply[T: BaseModel]:
    value: T | None
    """The validated output, or ``None`` when every attempt failed validation."""
    attempts: int
    errors: list[str] = field(default_factory=list)
    """Why each failed attempt was rejected, in order."""
    input_tokens: int = 0
    output_tokens: int = 0


def ask[T: BaseModel](
    gateway: ModelGateway,
    model: str,
    messages: Sequence[Message],
    output: type[T],
    *,
    retries: int,
    context: Mapping[str, Any] | None = None,
) -> StructuredReply[T]:
    """Ask for ``output`` as JSON and validate the reply, retrying up to ``retries`` times.

    A retry sends the rejected reply back with the validation error, so the model can
    correct it and the retry is a different prompt (and cache key) from the first try.
    ``context`` is passed to the output's validators.
    """
    conversation = [dict(m) for m in messages]
    reply: StructuredReply[T] = StructuredReply(value=None, attempts=0)
    while reply.attempts <= retries:
        chat = gateway.chat(model, conversation)
        reply.attempts += 1
        reply.input_tokens += chat.input_tokens
        reply.output_tokens += chat.output_tokens
        try:
            reply.value = output.model_validate(_parse_json(chat.text), context=context)
            return reply
        except (ValueError, ValidationError) as error:
            problem = _describe(error)
            reply.errors.append(problem)
        conversation += [
            {"role": "assistant", "content": chat.text},
            {
                "role": "user",
                "content": f"That reply was rejected: {problem}. "
                "Reply again with only the corrected JSON object.",
            },
        ]
    return reply


def _title(output: type[BaseModel]) -> str:
    return output.model_config.get("title") or output.__name__


def _parse_json(text: str) -> Any:
    """Parse a JSON object, tolerating a Markdown code fence around it."""
    text = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"not valid JSON ({error.msg} at position {error.pos})") from error


def _describe(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'object'}: {e['msg']}" for e in error.errors()
        )
    return str(error)
