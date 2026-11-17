"""Cached replay: an on-disk cache of model calls, keyed by model and prompt."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from casewise.gateway import ChatResult, Message, ModelGateway


class CacheMiss(LookupError):
    """A call was not in the cache and there is no provider to fall back to."""


class CachedGateway:
    """Serve model calls from ``cache_dir``.

    With a ``provider``, a miss calls it and records the answer (record mode).
    Without one, a miss raises :class:`CacheMiss` (replay mode), so a replay can
    never reach a live model.

    Each entry is one JSON file named by the SHA-256 of its key. Embeddings are
    cached per text, so a batch only sends the provider the texts it has not seen.
    """

    def __init__(self, cache_dir: Path, provider: ModelGateway | None = None) -> None:
        self._dir = Path(cache_dir)
        self._provider = provider

    def chat(self, model: str, messages: Sequence[Message]) -> ChatResult:
        key = {"kind": "chat", "model": model, "messages": [dict(m) for m in messages]}
        cached = self._read(key)
        if cached is not None:
            return ChatResult(**cached)
        result = self._require_provider(key).chat(model, messages)
        self._write(
            key,
            {
                "text": result.text,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )
        return result

    def embed(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        keys = [{"kind": "embed", "model": model, "text": text} for text in texts]
        vectors = [self._read(key) for key in keys]
        missing = [i for i, vector in enumerate(vectors) if vector is None]
        if missing:
            provider = self._require_provider(keys[missing[0]])
            fresh = provider.embed(model, [texts[i] for i in missing])
            for i, vector in zip(missing, fresh, strict=True):
                vectors[i] = list(vector)
                self._write(keys[i], vectors[i])
        return vectors

    def _require_provider(self, key: dict[str, Any]) -> ModelGateway:
        if self._provider is None:
            preview = json.dumps(key)[:200]
            raise CacheMiss(f"No cached {key['kind']} call in {self._dir} for {preview}")
        return self._provider

    def _path(self, key: dict[str, Any]) -> Path:
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()
        return self._dir / key["kind"] / f"{digest}.json"

    def _read(self, key: dict[str, Any]) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["value"]

    def _write(self, key: dict[str, Any], value: Any) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"key": key, "value": value}, indent=1), encoding="utf-8")
