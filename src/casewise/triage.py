"""Triage: decide whether a ticket gets an auto-reply or goes to a human.

Triage is a LangGraph state graph::

    safety_rules -> intent -> retrieve -> threshold_check -> grounding_check -> draft_reply
                                  |              |                 |               |
                                  +--------------+-----------------+---------------+
                                                 v  (escalated)
                                          draft_for_review

A step escalates by setting ``escalation`` in the graph state. Its reducer keeps the
first value written, so once a ticket is escalated no later step can undo it (ADR 3).
After an escalation only the steps that fill the handoff packet still run.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from casewise import structured
from casewise.config import Settings
from casewise.gateway import ModelGateway
from casewise.kb import Article, KnowledgeBase, Match, load_articles
from casewise.rules import RuleMatch, load_rules, matching_rules
from casewise.trace import Trace

INTENT_SYSTEM_PROMPT = (
    "You classify support tickets for a clinical practice-management product. "
    "Choose the one intent that best describes what the ticket asks for, from this "
    "list:\n{labels}\n"
    "Set confidence to your probability, from 0 to 1, that the intent is right."
)

GROUNDING_SYSTEM_PROMPT = (
    "You check whether a knowledge-base article answers a support ticket for a clinical "
    "practice-management product. Set answers_ticket to true only if following the "
    "article would resolve what the ticket actually asks. An article about a related "
    "task does not answer it: an article on placing an order does not answer a question "
    "about cancelling one. If the ticket asks for more than one thing, the article must "
    "answer all of them: an article that covers only part of the request does not answer "
    "it. Give the reason in one sentence."
)

DRAFT_SYSTEM_PROMPT = (
    "You are a support agent for a clinical practice-management product. "
    "Answer the customer's ticket using only the knowledge-base article provided. "
    "Be brief and concrete. Do not add steps or facts that are not in the article. "
    "Put the reply in reply and the article's id in cited_article_id."
)

REVIEW_DRAFT_SYSTEM_PROMPT = (
    "You are drafting a reply for a human support agent at a clinical practice-management "
    "product. The agent will review and edit it before anything is sent. "
    "The ticket was escalated to a human for this reason: {reason} "
    "Acknowledge the customer's problem and say a member of the support team is handling "
    "it. Do not promise an outcome or a timeline. Give product steps only if a "
    "knowledge-base article is provided and it answers the ticket, and take them only "
    "from that article. Put the reply in draft."
)

REVIEW_MARKER = "[FOR HUMAN REVIEW: suggested draft, not sent to the customer]"

OTHER_INTENT = "other"

NO_ARTICLE_STEP = (
    "No knowledge-base article is close enough to answer this. Answer it by hand, and "
    "flag the topic as a possible knowledge-base gap."
)

UNGROUNDED_STEP = (
    "The closest knowledge-base article looks related but does not answer this ticket. "
    "Answer it by hand, and flag the question as a possible knowledge-base gap."
)

INVALID_OUTPUT_STEP = (
    "The model's output for the {step} step failed validation, so this ticket was not "
    "checked automatically. Triage it by hand."
)


class Ticket(BaseModel):
    subject: str
    body: str
    requester_role: str | None = None
    practice_size: str | None = None
    plan_tier: str | None = None
    timestamp: datetime | None = None


class Intent(BaseModel):
    """What the ticket asks for. Labels are the knowledge-base article ids plus
    ``other``, until the topic taxonomy replaces them (see :func:`intent_labels`)."""

    model_config = ConfigDict(title="intent", extra="forbid")

    intent: str
    confidence: float = Field(ge=0, le=1)

    @field_validator("intent")
    @classmethod
    def _known_label(cls, value: str, info: ValidationInfo) -> str:
        labels = (info.context or {}).get("labels")
        if labels is not None and value not in labels:
            raise ValueError(f"must be one of: {', '.join(labels)}")
        return value


class GroundingVerdict(BaseModel):
    """Whether the best-matching article actually answers the ticket."""

    model_config = ConfigDict(title="grounding", extra="forbid")

    answers_ticket: bool
    reason: str = Field(min_length=1)


class Draft(BaseModel):
    """An auto-reply and the article it is based on."""

    model_config = ConfigDict(title="draft", extra="forbid")

    reply: str = Field(min_length=1)
    cited_article_id: str

    @field_validator("cited_article_id")
    @classmethod
    def _cites_the_given_article(cls, value: str, info: ValidationInfo) -> str:
        expected = (info.context or {}).get("article_id")
        if expected is not None and value != expected:
            raise ValueError(f"must cite the article provided, {expected!r}")
        return value


class ReviewDraft(BaseModel):
    """A suggested reply for the human agent who takes an escalation."""

    model_config = ConfigDict(title="review_draft", extra="forbid")

    draft: str = Field(min_length=1)


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
    """The intent label, or ``None`` if the intent step produced no valid output."""
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
    """Names the rule or check that escalated, e.g. ``safety_rule:billing_dispute: ...``,
    ``retrieval_threshold: ...`` or ``grounding_check: ...``. The same text as
    ``handoff.reason``."""
    intent: Intent | None = None
    """The classified intent, or ``None`` if the intent step produced no valid output."""
    grounding: GroundingVerdict | None = None
    """The grounding verdict, or ``None`` when the grounding check did not run."""
    handoff: HandoffPacket | None = None
    """Present on every escalation, absent on every auto-reply."""
    top_articles: list[RetrievedArticle] = []
    """The closest knowledge-base articles, best first, whatever the decision."""
    run_id: str
    trace_path: Path


class Escalation(BaseModel):
    reason: str
    next_step: str


def _first_escalation(current: Escalation | None, new: Escalation | None) -> Escalation | None:
    """An escalation, once made, is final: later writes never replace or clear it."""
    return current if current is not None else new


class TriageState(TypedDict, total=False):
    ticket: Ticket
    ticket_text: str
    fired: list[RuleMatch]
    escalation: Annotated[Escalation | None, _first_escalation]
    intent: Intent | None
    matches: list[Match]
    grounding: GroundingVerdict | None
    reply: str
    cited_article: CitedArticle
    handoff: HandoffPacket


def triage(
    ticket: Ticket, *, gateway: ModelGateway, settings: Settings | None = None
) -> TriageResult:
    """Triage one ticket. Every model call goes through ``gateway``.

    Safety rules run first. Once a ticket is escalated, by a rule or by any later check,
    the remaining steps only gather material for the handoff packet and cannot change
    the decision.

    Writes a JSONL trace of the run to ``settings.trace_dir``, one record per step.
    """
    settings = settings or Settings()
    trace = Trace(settings.trace_dir)
    articles = load_articles(settings.kb_dir)
    steps = _Steps(
        gateway=gateway,
        settings=settings,
        trace=trace,
        articles=articles,
        kb=KnowledgeBase(articles, gateway, settings.embedding_model),
    )
    final = _build_graph(steps).invoke(
        {"ticket": ticket, "ticket_text": f"{ticket.subject}\n\n{ticket.body}", "escalation": None}
    )
    escalation = final["escalation"]
    common = {
        "top_articles": _retrieved(final["matches"]),
        "intent": final.get("intent"),
        "grounding": final.get("grounding"),
        "run_id": trace.run_id,
        "trace_path": trace.path,
    }
    if escalation is not None:
        return TriageResult(
            decision="escalate",
            escalation_reason=escalation.reason,
            handoff=final["handoff"],
            **common,
        )
    return TriageResult(
        decision="auto_reply", reply=final["reply"], cited_article=final["cited_article"], **common
    )


def intent_labels(articles: list[Article]) -> dict[str, str]:
    """Intent labels and what each means. One per article, plus ``other``.

    The smallest set that works with a three-article knowledge base. When the topic
    taxonomy arrives, this is the one place to swap it in.
    """
    labels = {article.id: article.title for article in articles}
    labels[OTHER_INTENT] = "anything none of the above covers"
    return labels


def _build_graph(steps: _Steps) -> Any:
    graph = StateGraph(TriageState)
    for name in (
        "safety_rules",
        "intent",
        "retrieve",
        "threshold_check",
        "grounding_check",
        "draft_reply",
        "draft_for_review",
    ):
        graph.add_node(name, getattr(steps, name))
    graph.add_edge(START, "safety_rules")
    graph.add_edge("safety_rules", "intent")
    graph.add_edge("intent", "retrieve")
    for step, then in (
        ("retrieve", "threshold_check"),
        ("threshold_check", "grounding_check"),
        ("grounding_check", "draft_reply"),
        ("draft_reply", END),
    ):
        graph.add_conditional_edges(step, _unless_escalated(then), [then, "draft_for_review"])
    graph.add_edge("draft_for_review", END)
    return graph.compile()


def _unless_escalated(then: str):
    def route(state: TriageState) -> str:
        return "draft_for_review" if state.get("escalation") is not None else then

    return route


class _Steps:
    """The graph's nodes. Each traces itself and returns only the state it changes."""

    def __init__(
        self,
        *,
        gateway: ModelGateway,
        settings: Settings,
        trace: Trace,
        articles: list[Article],
        kb: KnowledgeBase,
    ) -> None:
        self.gateway = gateway
        self.settings = settings
        self.trace = trace
        self.articles = articles
        self.kb = kb

    def safety_rules(self, state: TriageState) -> dict[str, Any]:
        ticket = state["ticket"]
        with self.trace.step("safety_rules", {"ticket": ticket.model_dump(mode="json")}) as step:
            rules = load_rules(self.settings.rules_path)
            fired = matching_rules(rules, state["ticket_text"], ticket.requester_role)
            escalation = (
                Escalation(
                    reason=_rule_reason(fired), next_step=" ".join(fired[0].rule.next_step.split())
                )
                if fired
                else None
            )
            step.output = {
                "fired": [{"rule_id": match.rule.id, "phrase": match.phrase} for match in fired],
                "reason": escalation.reason if escalation else None,
            }
            step.decision = "escalate" if fired else "pass"
        return {"fired": fired, "escalation": escalation}

    def intent(self, state: TriageState) -> dict[str, Any]:
        labels = intent_labels(self.articles)
        listing = "\n".join(f"- {label}: {meaning}" for label, meaning in labels.items())
        messages = _messages(
            INTENT_SYSTEM_PROMPT.format(labels=listing), state["ticket_text"], Intent
        )
        with self.trace.step(
            "intent", {"model": self.settings.chat_model, "messages": messages}
        ) as step:
            reply = self._ask(step, messages, Intent, context={"labels": list(labels)})
            escalation = None
            if reply.value is None:
                escalation = _invalid_output("intent", reply)
            else:
                self.trace.intent = reply.value.model_dump()
            step.output = _reply_output(reply, escalation)
            # After a rule match this step informs the handoff only; it decides nothing.
            already_escalated = state.get("escalation") is not None
            step.decision = "escalate" if escalation and not already_escalated else "pass"
        return {"intent": reply.value, "escalation": escalation}

    def retrieve(self, state: TriageState) -> dict[str, Any]:
        with self.trace.step(
            "retrieve", {"ticket": state["ticket"].model_dump(mode="json")}
        ) as step:
            matches = self.kb.search(state["ticket_text"])
            step.output = {
                "matches": [
                    {"article_id": m.article.id, "title": m.article.title, "distance": m.distance}
                    for m in matches
                ]
            }
        return {"matches": matches}

    def threshold_check(self, state: TriageState) -> dict[str, Any]:
        best = state["matches"][0]
        threshold = self.settings.distance_threshold
        with self.trace.step(
            "threshold_check",
            {"article_id": best.article.id, "distance": best.distance, "threshold": threshold},
        ) as step:
            within = best.distance <= threshold
            escalation = None
            if not within:
                escalation = Escalation(
                    reason=(
                        f"retrieval_threshold: best match '{best.article.id}' is at cosine "
                        f"distance {best.distance:.3f}, beyond the threshold of {threshold}"
                    ),
                    next_step=NO_ARTICLE_STEP,
                )
            step.output = {
                "within_threshold": within,
                "reason": escalation.reason if escalation else None,
            }
            step.decision = "escalate" if escalation else "pass"
        return {"escalation": escalation}

    def grounding_check(self, state: TriageState) -> dict[str, Any]:
        article = state["matches"][0].article
        messages = _messages(
            GROUNDING_SYSTEM_PROMPT, _article_and_ticket(article, state["ticket_text"]),
            GroundingVerdict,
        )  # fmt: skip
        with self.trace.step(
            "grounding_check", {"model": self.settings.chat_model, "messages": messages}
        ) as step:
            reply = self._ask(step, messages, GroundingVerdict)
            verdict = reply.value
            escalation = None
            if verdict is None:
                escalation = _invalid_output("grounding_check", reply)
            else:
                self.trace.grounding = {"article_id": article.id, **verdict.model_dump()}
                if not verdict.answers_ticket:
                    escalation = Escalation(
                        reason=(
                            f"grounding_check: article '{article.id}' does not answer the "
                            f"ticket: {verdict.reason}"
                        ),
                        next_step=UNGROUNDED_STEP,
                    )
            step.output = _reply_output(reply, escalation)
            step.decision = "escalate" if escalation else "pass"
        return {"grounding": verdict, "escalation": escalation}

    def draft_reply(self, state: TriageState) -> dict[str, Any]:
        article = state["matches"][0].article
        messages = _messages(
            DRAFT_SYSTEM_PROMPT, _article_and_ticket(article, state["ticket_text"]), Draft
        )
        with self.trace.step(
            "draft_reply", {"model": self.settings.chat_model, "messages": messages}
        ) as step:
            reply = self._ask(step, messages, Draft, context={"article_id": article.id})
            if reply.value is None:
                escalation = _invalid_output("draft_reply", reply)
                step.output = _reply_output(reply, escalation)
                step.decision = "escalate"
                return {"escalation": escalation}
            text = f"{reply.value.reply.strip()}\n\n{_source_line(article)}"
            step.output = {
                "reply": text,
                "cited_article_id": article.id,
                "attempts": reply.attempts,
            }
            step.decision = "auto_reply"
        return {"reply": text, "cited_article": CitedArticle(id=article.id, title=article.title)}

    def draft_for_review(self, state: TriageState) -> dict[str, Any]:
        escalation = state["escalation"]
        matches = state["matches"]
        best = matches[0]
        grounding = state.get("grounding")
        answers = best.distance <= self.settings.distance_threshold and (
            grounding is None or grounding.answers_ticket
        )
        article = best.article if answers else None
        knowledge = f"Article: {article.title}\n{article.body}" if article else "Article: none"
        messages = _messages(
            REVIEW_DRAFT_SYSTEM_PROMPT.format(reason=escalation.reason),
            f"{knowledge}\n\nTicket:\n{state['ticket_text']}",
            ReviewDraft,
        )
        with self.trace.step(
            "draft_for_review", {"model": self.settings.chat_model, "messages": messages}
        ) as step:
            reply = self._ask(step, messages, ReviewDraft)
            if reply.value is None:
                body = (
                    f"No suggested draft: the model's output failed validation after "
                    f"{reply.attempts} attempts."
                )
            else:
                body = reply.value.draft.strip()
            suggested_draft = f"{REVIEW_MARKER}\n\n{body}"
            if article is not None and reply.value is not None:
                suggested_draft += f"\n\n{_source_line(article)}"
            intent = state.get("intent")
            handoff = HandoffPacket(
                reason=escalation.reason,
                triggered_rules=[match.rule.id for match in state["fired"]],
                detected_intent=intent.intent if intent else None,
                top_articles=_retrieved(matches),
                suggested_draft=suggested_draft,
                next_step=escalation.next_step,
            )
            step.output = {"handoff": handoff.model_dump(mode="json"), "attempts": reply.attempts}
            step.decision = "escalate"
        return {"handoff": handoff}

    def _ask[T: BaseModel](
        self, step, messages, output: type[T], *, context: dict[str, Any] | None = None
    ) -> structured.StructuredReply[T]:
        reply = structured.ask(
            self.gateway,
            self.settings.chat_model,
            messages,
            output,
            retries=self.settings.structured_output_retries,
            context=context,
        )
        step.record_tokens(reply.input_tokens, reply.output_tokens)
        return reply


def _messages(system: str, user: str, output: type[BaseModel]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": f"{system}\n\n{structured.output_instructions(output)}"},
        {"role": "user", "content": user},
    ]


def _article_and_ticket(article: Article, ticket_text: str) -> str:
    return (
        f"Article id: {article.id}\nArticle: {article.title}\n{article.body}\n\n"
        f"Ticket:\n{ticket_text}"
    )


def _retrieved(matches: list[Match]) -> list[RetrievedArticle]:
    return [
        RetrievedArticle(id=m.article.id, title=m.article.title, distance=m.distance)
        for m in matches
    ]


def _source_line(article: Article) -> str:
    return f"Source: {article.title} ({article.id})"


def _invalid_output(step: str, reply: structured.StructuredReply) -> Escalation:
    return Escalation(
        reason=(
            f"invalid_output:{step}: no valid output after {reply.attempts} attempts "
            f"(last error: {reply.errors[-1]})"
        ),
        next_step=INVALID_OUTPUT_STEP.format(step=step),
    )


def _reply_output(
    reply: structured.StructuredReply, escalation: Escalation | None
) -> dict[str, Any]:
    return {
        "value": reply.value.model_dump() if reply.value is not None else None,
        "attempts": reply.attempts,
        "errors": reply.errors,
        "reason": escalation.reason if escalation else None,
    }


def _rule_reason(fired: list[RuleMatch]) -> str:
    first, *others = (match.rule for match in fired)
    reason = f"safety_rule:{first.id}: {first.description}"
    if others:
        reason += f" (also matched: {', '.join(rule.id for rule in others)})"
    return reason
