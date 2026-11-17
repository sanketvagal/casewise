"""Run traces: one JSONL file per triage run, one record per step."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class Step:
    """One step being traced. Set ``output`` and ``decision`` (and ``tokens`` for model
    calls) before the ``with`` block ends."""

    def __init__(self, name: str, input: dict[str, Any]) -> None:
        self.name = name
        self.input = input
        self.output: dict[str, Any] = {}
        self.decision: str | None = None
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class Trace:
    """A run's trace file. Every record also carries the run's ``intent`` and
    ``grounding`` verdict as known when the step finished (``None`` until set)."""

    def __init__(self, trace_dir: Path) -> None:
        self.intent: dict[str, Any] | None = None
        self.grounding: dict[str, Any] | None = None
        self.run_id = uuid.uuid4().hex
        self.path = Path(trace_dir) / f"{self.run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch()

    def step(self, name: str, input: dict[str, Any]) -> _StepRecorder:
        return _StepRecorder(self, Step(name, input))

    def _write(self, step: Step, latency_ms: float) -> None:
        record = {
            "run_id": self.run_id,
            "step": step.name,
            "input": step.input,
            "output": step.output,
            "latency_ms": round(latency_ms, 3),
            "tokens": {"input": step.input_tokens, "output": step.output_tokens},
            "decision": step.decision,
            "intent": self.intent,
            "grounding": self.grounding,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")


class _StepRecorder:
    def __init__(self, trace: Trace, step: Step) -> None:
        self._trace = trace
        self._step = step

    def __enter__(self) -> Step:
        self._started = time.perf_counter()
        return self._step

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self._step.decision = "error"
            self._step.output = {"error": f"{exc_type.__name__}: {exc}"}
        self._trace._write(self._step, (time.perf_counter() - self._started) * 1000)
