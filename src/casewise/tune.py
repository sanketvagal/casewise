"""Tuning the retrieval threshold on weeks 1-2 only (ADR 7).

One evaluation run triages every weeks 1-2 ticket with no distance cut-off, so each
ticket's grounding check, draft and judge verdict are on record. Every candidate
threshold is then scored from that one run, with no further model calls: a threshold
only decides whether a ticket reaches the grounding check, and nothing before that
step depends on it.

The chosen threshold is the one with the highest deflection rate among those with no
unsafe auto-reply. Ties go to the smaller threshold.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel

from casewise.config import Settings
from casewise.evaluate import EvalResults, LabeledTicket, TicketOutcome, evaluate, score
from casewise.gateway import ModelGateway
from casewise.generate import WEEK_1_START

HELD_OUT_START = WEEK_1_START + timedelta(days=14)
"""Where weeks 3-4 begin. No ticket from here on may reach tuning."""

THRESHOLD_GRID: tuple[float, ...] = tuple(round(i * 0.01, 2) for i in range(101))
"""Candidate cosine-distance thresholds, 0.00 to 1.00 in steps of 0.01."""

NO_CUT_OFF = 2.0
"""The largest possible cosine distance: at this threshold every ticket passes the
threshold check and its later steps are recorded."""

OBJECTIVE = (
    "highest deflection rate with 0 unsafe auto-replies on weeks 1-2; "
    "ties go to the smaller threshold"
)

_DECIDED_BEFORE_THRESHOLD = ("safety_rule:", "invalid_output:intent:")
"""Escalation reasons from steps that run before the threshold check."""


class HeldOutTickets(ValueError):
    """Tuning was handed a ticket that is not from weeks 1-2."""


class SweepPoint(BaseModel):
    threshold: float
    auto_replies: int
    correct_auto_replies: int
    deflection_rate: float
    answer_accuracy: float
    unsafe_auto_replies: int
    escalation_recall: float


class TuningResult(BaseModel):
    threshold: float
    objective: str
    tickets: int
    chat_model: str
    judge_model: str
    sweep: list[SweepPoint]
    sweep_run: EvalResults
    """The run with no cut-off that every sweep point was scored from."""


def tune(
    labeled_tickets: Sequence[LabeledTicket],
    *,
    gateway: ModelGateway,
    judge_gateway: ModelGateway,
    settings: Settings | None = None,
) -> TuningResult:
    """Choose the distance threshold on weeks 1-2 tickets.

    Raises :class:`HeldOutTickets`, before any model call, if a ticket is undated or
    from weeks 3-4.
    """
    settings = settings or Settings()
    _refuse_held_out(labeled_tickets)
    run = evaluate(
        labeled_tickets,
        gateway=gateway,
        judge_gateway=judge_gateway,
        settings=replace(settings, distance_threshold=NO_CUT_OFF),
    )
    threshold, sweep = choose_threshold(run.outcomes)
    return TuningResult(
        threshold=threshold,
        objective=OBJECTIVE,
        tickets=len(labeled_tickets),
        chat_model=settings.chat_model,
        judge_model=settings.judge_model,
        sweep=sweep,
        sweep_run=run,
    )


def choose_threshold(
    outcomes: Sequence[TicketOutcome], grid: Sequence[float] = THRESHOLD_GRID
) -> tuple[float, list[SweepPoint]]:
    """Score each threshold in ``grid`` from a no-cut-off run and pick one (see module)."""
    sweep = [_point(t, score(at_threshold(outcomes, t))) for t in sorted(grid)]
    safe = [point for point in sweep if point.unsafe_auto_replies == 0]
    if not safe:
        raise ValueError("No threshold in the grid gives 0 unsafe auto-replies")
    best = max(point.deflection_rate for point in safe)
    return next(p.threshold for p in safe if p.deflection_rate == best), sweep


def at_threshold(outcomes: Sequence[TicketOutcome], threshold: float) -> list[TicketOutcome]:
    """What a no-cut-off run's outcomes would have been at ``threshold``.

    A ticket whose best match is beyond the threshold escalates at the threshold check,
    unless an earlier step (a safety rule, or invalid intent output) already escalated
    it. Every other outcome is unchanged.
    """
    return [_at_threshold(outcome, threshold) for outcome in outcomes]


def _at_threshold(outcome: TicketOutcome, threshold: float) -> TicketOutcome:
    decided_earlier = outcome.decision == "escalate" and (
        outcome.escalation_reason or ""
    ).startswith(_DECIDED_BEFORE_THRESHOLD)
    if decided_earlier or outcome.best_distance is None or outcome.best_distance <= threshold:
        return outcome
    return outcome.model_copy(
        update={
            "decision": "escalate",
            "escalation_reason": (
                f"retrieval_threshold: best match is at cosine distance "
                f"{outcome.best_distance:.3f}, beyond the threshold of {threshold}"
            ),
            "cited_article": None,
            "judge": None,
            "judge_reason": None,
        }
    )


def _point(threshold: float, metrics) -> SweepPoint:
    return SweepPoint(
        threshold=threshold,
        **metrics.model_dump(
            include={
                "auto_replies",
                "correct_auto_replies",
                "deflection_rate",
                "answer_accuracy",
                "unsafe_auto_replies",
                "escalation_recall",
            }
        ),
    )


def _refuse_held_out(labeled_tickets: Sequence[LabeledTicket]) -> None:
    # A timestamp with no time zone can't be placed on either side of the split, so it
    # is refused like an undated one.
    refused = [
        t.id
        for t in labeled_tickets
        if t.ticket.timestamp is None
        or t.ticket.timestamp.tzinfo is None
        or t.ticket.timestamp >= HELD_OUT_START
    ]
    if refused:
        shown = ", ".join(refused[:5]) + (
            f" and {len(refused) - 5} more" if len(refused) > 5 else ""
        )
        raise HeldOutTickets(
            f"Tuning only uses weeks 1-2 tickets (before {HELD_OUT_START:%Y-%m-%d}). "
            f"These are undated, naive (no time zone) or held out: {shown}"
        )


def write_tuning(result: TuningResult, out_dir: Path, name: str = "weeks-1-2") -> None:
    """Write ``<name>.json`` (choice, sweep and the sweep run's rows) and ``<name>.md``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(result.model_dump_json(indent=2) + "\n", "utf-8")
    (out_dir / f"{name}.md").write_text(tuning_markdown(result), encoding="utf-8")


def tuning_markdown(result: TuningResult) -> str:
    """The sweep as a table, trimmed to the thresholds where something changes."""
    rows, previous = [], None
    for point in result.sweep:
        key = point.model_dump(exclude={"threshold"})
        if key != previous or point.threshold == result.threshold:
            mark = " **chosen**" if point.threshold == result.threshold else ""
            rows.append(
                f"| {point.threshold:.2f}{mark} | {point.auto_replies} | "
                f"{point.correct_auto_replies} | {point.deflection_rate:.1%} | "
                f"{point.answer_accuracy:.1%} | {point.unsafe_auto_replies} | "
                f"{point.escalation_recall:.1%} |"
            )
        previous = key
    # With no cut-off, these got past the rules and the grounding check. Only the
    # threshold stands between them and an unsafe auto-reply.
    caught_only_by_threshold = sorted(
        (o for o in result.sweep_run.outcomes
         if o.decision == "auto_reply" and o.labeled.must_escalate),
        key=lambda o: o.best_distance or 0.0,
    )  # fmt: skip
    lines = [
        "# Threshold tuning, weeks 1-2",
        "",
        f"{result.tickets} tickets. Triage `{result.chat_model}`, judge "
        f"`{result.judge_model}`. See ADR 7.",
        "",
        f"Chosen distance threshold: **{result.threshold:.2f}** ({result.objective}).",
        "",
        "Rows are shown only where a metric changes.",
        "",
        "| Threshold | Auto-replies | Correct | Deflection | Accuracy | Unsafe | Esc. recall |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        *rows,
        "",
        "## Must-escalate tickets that only the threshold stops",
        "",
        "With no cut-off these were auto-replied: no safety rule fired and the grounding "
        f"check passed. {len(caught_only_by_threshold)} tickets.",
        "",
    ]
    lines += [
        f"- `{o.labeled.id}` at {o.best_distance:.3f}, cited `{o.cited_article}`, "
        f"labeled `{o.labeled.escalation_reason}`: {o.labeled.ticket.subject}"
        for o in caught_only_by_threshold
    ]
    return "\n".join([*lines, ""])
