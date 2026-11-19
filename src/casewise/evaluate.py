"""Evaluation: run triage over labeled tickets, judge the auto-replies, and score the run.

The metric definitions are ADR 5. In short, an auto-reply is correct only when the
ticket is not must-escalate, it cites the labeled answering article, and the judge
says it is correct. Deflection counts only correct auto-replies.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from casewise import structured
from casewise.config import Settings
from casewise.gateway import ModelGateway
from casewise.kb import Article, load_articles
from casewise.triage import Ticket, TriageResult, triage

JUDGE_SYSTEM_PROMPT = (
    "You grade a support auto-reply for a clinical practice-management product against "
    "the knowledge-base article that answers the ticket. Mark it correct only if all of "
    "these hold: it answers what the ticket actually asks; it agrees with the article; "
    "and it adds no steps, facts or promises that the article does not support. "
    "Otherwise mark it incorrect. Give the reason in one sentence."
)


class LabeledTicket(BaseModel):
    """A ticket with its known-correct answers."""

    id: str
    ticket: Ticket
    intent: str
    answering_article: str | None
    """The article that truly answers the ticket, or ``None`` if none does."""
    must_escalate: bool
    """True when a safety rule applies or no article answers the ticket."""
    escalation_reason: str | None = None
    """A safety rule id, or ``no_answer``. Set on must-escalate tickets."""


JudgeOutcome = Literal["correct", "incorrect", "unjudged"]


class TicketOutcome(BaseModel):
    """What happened to one labeled ticket during an evaluation run."""

    labeled: LabeledTicket
    decision: Literal["auto_reply", "escalate"]
    cited_article: str | None = None
    escalation_reason: str | None = None
    predicted_intent: str | None = None
    """``None`` when the intent step produced no valid output."""
    judge: JudgeOutcome | None = None
    """The judge's verdict, or ``None`` when the judge was not called."""
    judge_reason: str | None = None

    @computed_field
    @property
    def escalation_reason_matches(self) -> bool | None:
        """Whether an escalated must-escalate ticket escalated for its labeled reason.
        ``None`` for any other ticket. Informational: it scores nothing (ADR 5)."""
        if not (self.labeled.must_escalate and self.decision == "escalate"):
            return None
        return _reason_category(self.escalation_reason) == self.labeled.escalation_reason

    @computed_field
    @property
    def correct(self) -> bool:
        """A correct auto-reply (ADR 5). Always false for an escalation."""
        return (
            self.decision == "auto_reply"
            and not self.labeled.must_escalate
            and self.cited_article == self.labeled.answering_article
            and self.judge == "correct"
        )


class Metrics(BaseModel):
    tickets: int
    auto_replies: int
    correct_auto_replies: int
    deflection_rate: float
    """Correct auto-replies / all tickets."""
    answer_accuracy: float
    """Correct auto-replies / all auto-replies."""
    unsafe_auto_replies: int
    """Auto-replies on must-escalate tickets. The target is 0."""
    unjudged: int
    """Auto-replies the judge gave no valid verdict for. Each counts as incorrect."""
    confusion: dict[Decision, dict[Decision, int]]
    """``confusion[label][decision]``: the label is ``escalate`` for must-escalate tickets."""
    precision: dict[Decision, float]
    recall: dict[Decision, float]
    escalation_recall: float
    """Escalations on must-escalate tickets / all must-escalate tickets. The target is 1."""
    intent_macro_f1: float
    """F1 per intent class present in the gold labels, averaged. Invalid intent output
    counts as a wrong prediction."""
    escalation_reason_agreement: float
    """Share of escalated must-escalate tickets that escalated for their labeled reason.
    Informational only."""


NO_ANSWER = "no_answer"
"""The labeled escalation reason for a ticket no knowledge-base article answers."""

_NO_ANSWER_CHECKS = ("retrieval_threshold", "grounding_check")


def _reason_category(reason: str | None) -> str | None:
    """Map a triage escalation reason onto the labeled vocabulary: a safety rule id, or
    ``no_answer`` for the two confidence checks. Invalid output maps to ``None``."""
    if reason is None:
        return None
    head, _, rest = reason.partition(":")
    if head == "safety_rule":
        return rest.split(":", 1)[0]
    if head in _NO_ANSWER_CHECKS:
        return NO_ANSWER
    return None


Decision = Literal["auto_reply", "escalate"]
DECISIONS: tuple[Decision, ...] = ("auto_reply", "escalate")


def score(outcomes: list[TicketOutcome]) -> Metrics:
    """Score an evaluation run (ADR 5). A ratio with nothing to divide by is 0."""
    replies = [o for o in outcomes if o.decision == "auto_reply"]
    correct = sum(o.correct for o in replies)
    confusion = {label: dict.fromkeys(DECISIONS, 0) for label in DECISIONS}
    for o in outcomes:
        confusion[_routing_label(o)][o.decision] += 1
    precision = {
        d: _ratio(confusion[d][d], sum(confusion[label][d] for label in DECISIONS))
        for d in DECISIONS
    }
    recall = {d: _ratio(confusion[d][d], sum(confusion[d].values())) for d in DECISIONS}
    matches = [
        o.escalation_reason_matches for o in outcomes if o.escalation_reason_matches is not None
    ]
    return Metrics(
        confusion=confusion,
        precision=precision,
        recall=recall,
        escalation_recall=recall["escalate"],
        intent_macro_f1=_macro_f1([(o.labeled.intent, o.predicted_intent) for o in outcomes]),
        escalation_reason_agreement=_ratio(sum(m is True for m in matches), len(matches)),
        tickets=len(outcomes),
        auto_replies=len(replies),
        correct_auto_replies=correct,
        deflection_rate=_ratio(correct, len(outcomes)),
        answer_accuracy=_ratio(correct, len(replies)),
        unsafe_auto_replies=sum(o.labeled.must_escalate for o in replies),
        unjudged=sum(o.judge == "unjudged" for o in replies),
    )


def _macro_f1(pairs: list[tuple[str, str | None]]) -> float:
    """Macro-F1 over the gold classes. ``None`` (no valid prediction) is always wrong."""
    gold_classes = sorted({gold for gold, _ in pairs})
    f1s = []
    for label in gold_classes:
        tp = sum(g == label and p == label for g, p in pairs)
        predicted = sum(p == label for _, p in pairs)
        actual = sum(g == label for g, _ in pairs)
        precision, recall = _ratio(tp, predicted), _ratio(tp, actual)
        f1s.append(_ratio(2 * precision * recall, precision + recall))
    return sum(f1s) / len(f1s) if f1s else 0.0


def _routing_label(outcome: TicketOutcome) -> Decision:
    return "escalate" if outcome.labeled.must_escalate else "auto_reply"


def _ratio(part: float, whole: float) -> float:
    return part / whole if whole else 0.0


class JudgeVerdict(BaseModel):
    """The judge's grade for one auto-reply."""

    model_config = ConfigDict(title="judge", extra="forbid")

    verdict: Literal["correct", "incorrect"]
    reason: str = Field(min_length=1)


class EvalResults(BaseModel):
    metrics: Metrics
    outcomes: list[TicketOutcome]


def evaluate(
    labeled_tickets: Sequence[LabeledTicket],
    *,
    gateway: ModelGateway,
    judge_gateway: ModelGateway,
    settings: Settings | None = None,
) -> EvalResults:
    """Triage every labeled ticket through ``gateway``, judge the auto-replies through
    ``judge_gateway`` and score the run (ADR 5).

    The judge is only asked about an auto-reply that could be correct: one on a ticket
    that is not must-escalate and that cites the labeled answering article. It is shown
    the ticket, the reply and that labeled article.
    """
    settings = settings or Settings()
    articles = {article.id: article for article in load_articles(settings.kb_dir)}
    outcomes = []
    for labeled in labeled_tickets:
        result = triage(labeled.ticket, gateway=gateway, settings=settings)
        outcome = _outcome(labeled, result)
        if _worth_judging(outcome):
            outcome = _judged(outcome, result, articles[labeled.answering_article],
                              judge_gateway, settings)  # fmt: skip
        outcomes.append(outcome)
    return EvalResults(metrics=score(outcomes), outcomes=outcomes)


def _outcome(labeled: LabeledTicket, result: TriageResult) -> TicketOutcome:
    return TicketOutcome(
        labeled=labeled,
        decision=result.decision,
        cited_article=result.cited_article.id if result.cited_article else None,
        escalation_reason=result.escalation_reason,
        predicted_intent=result.intent.intent if result.intent else None,
    )


def _worth_judging(outcome: TicketOutcome) -> bool:
    return (
        outcome.decision == "auto_reply"
        and not outcome.labeled.must_escalate
        and outcome.cited_article == outcome.labeled.answering_article
    )


def _judged(
    outcome: TicketOutcome,
    result: TriageResult,
    article: Article,
    judge_gateway: ModelGateway,
    settings: Settings,
) -> TicketOutcome:
    ticket = outcome.labeled.ticket
    user = (
        f"Article id: {article.id}\nArticle: {article.title}\n{article.body}\n\n"
        f"Ticket:\n{ticket.subject}\n\n{ticket.body}\n\n"
        f"Auto-reply:\n{result.reply}"
    )
    messages = [
        {
            "role": "system",
            "content": f"{JUDGE_SYSTEM_PROMPT}\n\n{structured.output_instructions(JudgeVerdict)}",
        },
        {"role": "user", "content": user},
    ]
    reply = structured.ask(
        judge_gateway, settings.judge_model, messages, JudgeVerdict,
        retries=settings.structured_output_retries,
    )  # fmt: skip
    if reply.value is None:
        return outcome.model_copy(
            update={"judge": "unjudged", "judge_reason": f"no valid verdict: {reply.errors[-1]}"}
        )
    return outcome.model_copy(
        update={"judge": reply.value.verdict, "judge_reason": reply.value.reason}
    )


def load_labeled_tickets(path: Path) -> list[LabeledTicket]:
    """Read labeled tickets from a JSONL file, one per line. Blank lines are skipped."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [LabeledTicket.model_validate_json(line) for line in lines if line.strip()]


def write_results(results: EvalResults, out_dir: Path) -> None:
    """Write ``latest.json`` (metrics and one row per ticket) and ``latest.md``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(results.model_dump_json(indent=2) + "\n", "utf-8")
    (out_dir / "latest.md").write_text(summary_markdown(results), encoding="utf-8")


def summary_markdown(results: EvalResults) -> str:
    """A readable summary of an evaluation run."""
    m = results.metrics
    c = m.confusion

    def pct(value: float) -> str:
        return f"{value:.1%}"

    lines = [
        "# Evaluation results",
        "",
        f"{m.tickets} tickets, {m.auto_replies} auto-replies, {m.correct_auto_replies} correct.",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Deflection rate | {pct(m.deflection_rate)} |",
        f"| Answer accuracy | {pct(m.answer_accuracy)} |",
        f"| Unsafe auto-replies | {m.unsafe_auto_replies} |",
        "",
        "## Routing",
        "",
        "| Label \\ Decision | auto_reply | escalate |",
        "| --- | --- | --- |",
        f"| auto_reply | {c['auto_reply']['auto_reply']} | {c['auto_reply']['escalate']} |",
        f"| escalate (must-escalate) | {c['escalate']['auto_reply']} "
        f"| {c['escalate']['escalate']} |",
        "",
        "| Class | Precision | Recall |",
        "| --- | --- | --- |",
        *(f"| {d} | {pct(m.precision[d])} | {pct(m.recall[d])} |" for d in DECISIONS),
        "",
        f"Escalation recall: {pct(m.escalation_recall)}",
        "",
        "## Other",
        "",
        f"- Intent macro-F1: {m.intent_macro_f1:.3f}",
        f"- Unjudged auto-replies (counted incorrect): {m.unjudged}",
        f"- Escalation reason agreement (informational): {pct(m.escalation_reason_agreement)}",
        "",
    ]
    wrong = [o for o in results.outcomes if o.decision == "auto_reply" and not o.correct]
    if wrong:
        lines += ["## Incorrect auto-replies", ""]
        lines += [
            f"- `{o.labeled.id}`: cited `{o.cited_article}`, labeled "
            f"`{o.labeled.answering_article}`, judge {o.judge or 'not asked'}"
            + (f": {o.judge_reason}" if o.judge_reason else "")
            for o in wrong
        ]
        lines.append("")
    return "\n".join(lines)
