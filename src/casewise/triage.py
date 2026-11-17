"""Triage: decide whether a ticket gets an auto-reply or goes to a human."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from casewise.config import Settings
from casewise.gateway import ModelGateway
from casewise.kb import Article, KnowledgeBase, load_articles
from casewise.trace import Trace

DRAFT_SYSTEM_PROMPT = (
    "You are a support agent for a clinical practice-management product. "
    "Answer the customer's ticket using only the knowledge-base article provided. "
    "Be brief and concrete. Do not add steps or facts that are not in the article."
)


class Ticket(BaseModel):
    subject: str
    body: str
    requester_role: str | None = None
    practice_size: str | None = None
    plan_tier: str | None = None
    timestamp: datetime | None = None


class CitedArticle(BaseModel):
    id: str
    title: str


class TriageResult(BaseModel):
    decision: Literal["auto_reply", "escalate"]
    reply: str | None = None
    """The auto-reply, ending with a citation of its article."""
    cited_article: CitedArticle | None = None
    escalation_reason: str | None = None
    """Names the check that failed, e.g. ``retrieval_threshold: ...``."""
    run_id: str
    trace_path: Path


def triage(
    ticket: Ticket, *, gateway: ModelGateway, settings: Settings | None = None
) -> TriageResult:
    """Triage one ticket. Every model call goes through ``gateway``.

    Writes a JSONL trace of the run to ``settings.trace_dir``, one record per step.
    """
    settings = settings or Settings()
    trace = Trace(settings.trace_dir)
    kb = KnowledgeBase(load_articles(settings.kb_dir), gateway, settings.embedding_model)
    ticket_text = f"{ticket.subject}\n\n{ticket.body}"

    with trace.step("retrieve", {"ticket": ticket.model_dump(mode="json")}) as step:
        matches = kb.search(ticket_text)
        best = matches[0]
        step.output = {
            "matches": [
                {"article_id": m.article.id, "title": m.article.title, "distance": m.distance}
                for m in matches
            ]
        }

    threshold = settings.distance_threshold
    with trace.step(
        "threshold_check",
        {"article_id": best.article.id, "distance": best.distance, "threshold": threshold},
    ) as step:
        escalation_reason = None
        if best.distance > threshold:
            escalation_reason = (
                f"retrieval_threshold: best match '{best.article.id}' is at cosine distance "
                f"{best.distance:.3f}, beyond the threshold of {threshold}"
            )
        step.output = {"within_threshold": escalation_reason is None, "reason": escalation_reason}
        step.decision = "escalate" if escalation_reason else "pass"

    if escalation_reason:
        return TriageResult(
            decision="escalate",
            escalation_reason=escalation_reason,
            run_id=trace.run_id,
            trace_path=trace.path,
        )

    messages = _draft_messages(ticket_text, best.article)
    with trace.step("draft_reply", {"model": settings.chat_model, "messages": messages}) as step:
        draft = gateway.chat(settings.chat_model, messages)
        reply = f"{draft.text.strip()}\n\nSource: {best.article.title} ({best.article.id})"
        step.record_tokens(draft.input_tokens, draft.output_tokens)
        step.output = {"reply": reply, "cited_article_id": best.article.id}
        step.decision = "auto_reply"

    return TriageResult(
        decision="auto_reply",
        reply=reply,
        cited_article=CitedArticle(id=best.article.id, title=best.article.title),
        run_id=trace.run_id,
        trace_path=trace.path,
    )


def _draft_messages(ticket_text: str, article: Article) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Article: {article.title}\n{article.body}\n\nTicket:\n{ticket_text}",
        },
    ]
