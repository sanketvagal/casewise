"""Triage driven through its public entry point with the scripted fake gateway."""

import json

import pytest

import replies as say
from casewise import ScriptedGateway, Settings, Ticket, triage
from paths import FIXTURE_KB

# Embedding directions the fake hands out. Texts mentioning a keyword point along
# that axis; anything else points along a fourth axis, far from every article.
TOPIC_VECTORS = {
    "password": [1.0, 0.0, 0.0, 0.0],
    "appointment": [0.0, 1.0, 0.0, 0.0],
    "invoice": [0.0, 0.0, 1.0, 0.0],
}
UNRELATED = [0.0, 0.0, 0.0, 1.0]


@pytest.fixture
def settings(tmp_path):
    return Settings(trace_dir=tmp_path / "traces", cache_dir=tmp_path / "cache", kb_dir=FIXTURE_KB)


def fake_gateway(**replies) -> ScriptedGateway:
    """A fake whose model says ``replies[step]`` at each step (see ``replies.py``)."""
    return ScriptedGateway(
        chat_replies=replies, embeddings=TOPIC_VECTORS, default_embedding=UNRELATED
    )


def password_gateway() -> ScriptedGateway:
    return fake_gateway(
        intent=say.intent("reset-password"),
        grounding=say.grounded(),
        draft=say.draft("Select Forgot password on the sign-in page.", "reset-password"),
    )


PASSWORD_TICKET = Ticket(
    subject="Locked out",
    body="I forgot my password and can't sign in. How do I reset it?",
    requester_role="front desk",
    practice_size="small",
    plan_tier="standard",
)

FAX_TICKET = Ticket(
    subject="Fax integration",
    body="Can the system send referral letters by fax to a specialist?",
    requester_role="practice admin",
)


def test_close_match_auto_replies_and_cites_its_article(settings):
    result = triage(PASSWORD_TICKET, gateway=password_gateway(), settings=settings)

    assert result.decision == "auto_reply"
    assert "Select Forgot password on the sign-in page." in result.reply
    assert result.cited_article.id == "reset-password"
    assert result.cited_article.title == "Reset a staff member's password"
    assert "Reset a staff member's password" in result.reply


def escalation_gateway(intent: str = "other") -> ScriptedGateway:
    """A fake for runs that escalate: only intent and the review draft are asked."""
    return fake_gateway(
        intent=say.intent(intent),
        review_draft=say.review_draft("Thanks, a colleague will pick this up."),
    )


def test_weak_match_escalates(settings):
    result = triage(FAX_TICKET, gateway=escalation_gateway(), settings=settings)

    assert result.decision == "escalate"
    assert result.reply is None
    assert result.cited_article is None
    assert "retrieval_threshold" in result.escalation_reason


def read_trace(result) -> list[dict]:
    return [json.loads(line) for line in result.trace_path.read_text().splitlines()]


def test_auto_reply_run_writes_one_trace_record_per_step(settings):
    result = triage(PASSWORD_TICKET, gateway=password_gateway(), settings=settings)

    records = read_trace(result)
    assert [r["step"] for r in records] == [
        "safety_rules",
        "intent",
        "retrieve",
        "threshold_check",
        "grounding_check",
        "draft_reply",
    ]
    for record in records:
        assert record["run_id"] == result.run_id
        assert record["input"] and record["output"]
        assert record["latency_ms"] >= 0
        assert set(record["tokens"]) == {"input", "output"}
    rules, intent, retrieve, threshold, grounding, draft = records
    assert rules["decision"] == "pass"
    assert intent["decision"] == "pass"
    assert retrieve["output"]["matches"][0]["article_id"] == "reset-password"
    assert threshold["decision"] == "pass"
    assert grounding["decision"] == "pass"
    assert draft["decision"] == "auto_reply"
    assert draft["output"]["reply"] == result.reply
    # The fake counts words; the scripted draft is JSON of ten whitespace-separated words.
    assert draft["tokens"]["output"] == 10


def test_every_trace_record_carries_the_intent_and_grounding_verdict(settings):
    result = triage(PASSWORD_TICKET, gateway=password_gateway(), settings=settings)

    records = {r["step"]: r for r in read_trace(result)}
    assert records["safety_rules"]["intent"] is None  # not classified yet
    for step in ("intent", "retrieve", "threshold_check", "grounding_check", "draft_reply"):
        assert records[step]["intent"] == {"intent": "reset-password", "confidence": 0.9}
    assert records["threshold_check"]["grounding"] is None  # not checked yet
    assert records["draft_reply"]["grounding"] == {
        "article_id": "reset-password",
        "answers_ticket": True,
        "reason": "The article answers exactly what the ticket asks.",
    }
    assert result.intent.intent == "reset-password"
    assert result.grounding.answers_ticket is True


def test_escalated_run_traces_the_failed_threshold_check(settings):
    result = triage(FAX_TICKET, gateway=escalation_gateway(), settings=settings)

    records = read_trace(result)
    assert [r["step"] for r in records] == [
        "safety_rules",
        "intent",
        "retrieve",
        "threshold_check",
        "draft_for_review",
    ]
    threshold, handoff = records[3:]
    assert threshold["decision"] == "escalate"
    assert threshold["output"]["reason"] == result.escalation_reason
    assert handoff["decision"] == "escalate"
    assert handoff["output"]["handoff"]["suggested_draft"] == result.handoff.suggested_draft
    assert handoff["tokens"]["output"] == 8  # the fake counts words in its scripted JSON
    assert handoff["intent"] == {"intent": "other", "confidence": 0.9}
    assert handoff["grounding"] is None  # nothing within the threshold to ground


def test_rule_escalation_traces_the_rule_and_skips_the_model_decision_steps(settings):
    ticket = Ticket(
        subject="Billing",
        body="We were charged twice for our appointment reminders add-on.",
        requester_role="biller",
    )
    result = triage(ticket, gateway=escalation_gateway(), settings=settings)

    records = read_trace(result)
    assert [r["step"] for r in records] == [
        "safety_rules",
        "intent",
        "retrieve",
        "draft_for_review",
    ]
    rules = records[0]
    assert rules["decision"] == "escalate"
    assert rules["output"]["fired"] == [{"rule_id": "billing_dispute", "phrase": "charged twice"}]
    assert records[-1]["decision"] == "escalate"
    assert records[-1]["output"]["handoff"]["reason"] == result.escalation_reason
