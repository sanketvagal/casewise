"""Triage: decide whether a ticket gets an auto-reply or goes to a human."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from casewise.config import Settings
from casewise.gateway import ModelGateway
from casewise.kb import Article, KnowledgeBase, load_articles
from casewise.rules import RuleMatch, load_rules, matching_rules
from casewise.trace import Trace

DRAFT_SYSTEM_PROMPT = (
    "You are a support agent for a clinical practice-management product. "
    "Answer the customer's ticket using only the knowledge-base article provided. "
    "Be brief and concrete. Do not add steps or facts that are not in the article."
)

REVIEW_DRAFT_SYSTEM_PROMPT = (
    "You are drafting a reply for a human support agent at a clinical practice-management "
    "product. The agent will review and edit it before anything is sent. "
    "The ticket was escalated to a human for this reason: {reason} "
    "Acknowledge the customer's problem and say a member of the support team is handling "
    "it. Do not promise an outcome or a timeline. Give product steps only if a "
    "knowledge-base article is provided and it answers the ticket, and take them only "
    "from that article."
)

REVIEW_MARKER = "[FOR HUMAN REVIEW: suggested draft, not sent to the customer]"

NO_ARTICLE_STEP = (
    "No knowledge-base article is close enough to answer this. Answer it by hand, and "
    "flag the topic as a possible knowledge-base gap."
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


class RetrievedArticle(BaseModel):
    id: str
    title: str
    distance: float
    """Cosine distance to the ticket: 0 is identical, 1 is unrelated."""


class HandoffPacket(BaseModel):
    """What the human agent receives with an escalated ticket."""

    reason: str
    """Names the safety rule or check that escalated the ticket."""
    triggered_rules: list[str]
    """Ids of every safety rule that matched; empty when a check escalated instead."""
    detected_intent: str | None = None
    top_articles: list[RetrievedArticle]
    """The closest knowledge-base articles, best first."""
    suggested_draft: str
    """A draft for the agent to edit. Marked for human review; never sent as-is."""
    next_step: str


class TriageResult(BaseModel):
    decision: Literal["auto_reply", "escalate"]
    reply: str | None = None
    """The auto-reply, ending with a citation of its article."""
    cited_article: CitedArticle | None = None
    escalation_reason: str | None = None
    """Names the rule or check that escalated, e.g. ``safety_rule:billing_dispute: ...``
    or ``retrieval_threshold: ...``. The same text as ``handoff.reason``."""
    handoff: HandoffPacket | None = None
    """Present on every escalation, absent on every auto-reply."""
    run_id: str
    trace_path: Path


def triage(
    ticket: Ticket, *, gateway: ModelGateway, settings: Settings | None = None
) -> TriageResult:
    """Triage one ticket. Every model call goes through ``gateway``.

    Safety rules run first. Once one matches, the ticket is escalated: the remaining
    steps only gather material for the handoff packet and cannot change the decision.

    Writes a JSONL trace of the run to ``settings.trace_dir``, one record per step.
    """
    settings = settings or Settings()
    trace = Trace(settings.trace_dir)
    kb = KnowledgeBase(load_articles(settings.kb_dir), gateway, settings.embedding_model)
    ticket_text = f"{ticket.subject}\n\n{ticket.body}"

    with trace.step("safety_rules", {"ticket": ticket.model_dump(mode="json")}) as step:
        fired = matching_rules(load_rules(settings.rules_path), ticket_text, ticket.requester_role)
        escalation_reason = _rule_reason(fired) if fired else None
        step.output = {
            "fired": [{"rule_id": match.rule.id, "phrase": match.phrase} for match in fired],
            "reason": escalation_reason,
        }
        step.decision = "escalate" if fired else "pass"

    with trace.step("retrieve", {"ticket": ticket.model_dump(mode="json")}) as step:
        matches = kb.search(ticket_text)
        best = matches[0]
        top_articles = [
            RetrievedArticle(id=m.article.id, title=m.article.title, distance=m.distance)
            for m in matches
        ]
        step.output = {
            "matches": [
                {"article_id": a.id, "title": a.title, "distance": a.distance} for a in top_articles
            ]
        }

    threshold = settings.distance_threshold
    within_threshold = best.distance <= threshold
    if escalation_reason is None:
        with trace.step(
            "threshold_check",
            {"article_id": best.article.id, "distance": best.distance, "threshold": threshold},
        ) as step:
            if not within_threshold:
                escalation_reason = (
                    f"retrieval_threshold: best match '{best.article.id}' is at cosine "
                    f"distance {best.distance:.3f}, beyond the threshold of {threshold}"
                )
            step.output = {"within_threshold": within_threshold, "reason": escalation_reason}
            step.decision = "escalate" if escalation_reason else "pass"

    source_line = f"Source: {best.article.title} ({best.article.id})"

    if escalation_reason is not None:
        article = best.article if within_threshold else None
        messages = _review_draft_messages(ticket_text, escalation_reason, article)
        with trace.step(
            "draft_for_review", {"model": settings.chat_model, "messages": messages}
        ) as step:
            draft = gateway.chat(settings.chat_model, messages)
            suggested_draft = f"{REVIEW_MARKER}\n\n{draft.text.strip()}"
            if article is not None:
                suggested_draft += f"\n\n{source_line}"
            handoff = HandoffPacket(
                reason=escalation_reason,
                triggered_rules=[match.rule.id for match in fired],
                top_articles=top_articles,
                suggested_draft=suggested_draft,
                next_step=" ".join(fired[0].rule.next_step.split()) if fired else NO_ARTICLE_STEP,
            )
            step.record_tokens(draft.input_tokens, draft.output_tokens)
            step.output = {"handoff": handoff.model_dump(mode="json")}
            step.decision = "escalate"
        return TriageResult(
            decision="escalate",
            escalation_reason=escalation_reason,
            handoff=handoff,
            run_id=trace.run_id,
            trace_path=trace.path,
        )

    messages = _draft_messages(ticket_text, best.article)
    with trace.step("draft_reply", {"model": settings.chat_model, "messages": messages}) as step:
        draft = gateway.chat(settings.chat_model, messages)
        reply = f"{draft.text.strip()}\n\n{source_line}"
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


def _rule_reason(fired: list[RuleMatch]) -> str:
    first, *others = (match.rule for match in fired)
    reason = f"safety_rule:{first.id}: {first.description}"
    if others:
        reason += f" (also matched: {', '.join(rule.id for rule in others)})"
    return reason


def _draft_messages(ticket_text: str, article: Article) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Article: {article.title}\n{article.body}\n\nTicket:\n{ticket_text}",
        },
    ]


def _review_draft_messages(
    ticket_text: str, reason: str, article: Article | None
) -> list[dict[str, str]]:
    knowledge = f"Article: {article.title}\n{article.body}" if article else "Article: none"
    return [
        {"role": "system", "content": REVIEW_DRAFT_SYSTEM_PROMPT.format(reason=reason)},
        {"role": "user", "content": f"{knowledge}\n\nTicket:\n{ticket_text}"},
    ]
