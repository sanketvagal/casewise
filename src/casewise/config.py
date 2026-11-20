"""Configuration. Every setting can be overridden by a ``CASEWISE_*`` environment variable."""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    provider: str = "groq"
    """Chat provider used by the live gateway."""
    chat_model: str = "openai/gpt-oss-120b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    judge_provider: str = "gemini"
    """Chat provider for the evaluation judge: a different model family from triage (ADR 5)."""
    judge_model: str = "gemini-3.5-flash-lite"
    generator_provider: str = "gemini"
    """Chat provider that writes the generated data: a different family from triage (ADR 6)."""
    generator_model: str = "gemini-3.5-flash-lite"
    gateway_mode: str = "record"
    """``live`` (no cache), ``record`` (cache, calling the provider on a miss) or
    ``replay`` (cache only, never calls a provider)."""
    distance_threshold: float = 0.5
    """Largest cosine distance at which the best article still counts as a match.
    A placeholder until it is tuned on weeks 1-2."""
    structured_output_retries: int = 2
    """How many times a model step is re-asked after output that fails validation.
    When every attempt fails, the ticket escalates."""
    kb_dir: Path = Path("kb")
    rules_path: Path = Path("safety_rules.yaml")
    """The safety rules: tickets that always escalate, whatever a model says."""
    cache_dir: Path = Path("cache")
    trace_dir: Path = Path("traces")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        overrides = {}
        for field in fields(cls):
            raw = env.get(f"CASEWISE_{field.name.upper()}")
            if raw is not None:
                overrides[field.name] = type(field.default)(raw)
        return cls(**overrides)
