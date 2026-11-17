"""Triage driven through its public entry point with the scripted fake gateway."""

import json

import pytest

from casewise import ScriptedGateway, Settings, Ticket, triage

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
    return Settings(trace_dir=tmp_path / "traces", cache_dir=tmp_path / "cache")


def fake_gateway(*chat_replies: str) -> ScriptedGateway:
    return ScriptedGateway(
        chat_replies=list(chat_replies), embeddings=TOPIC_VECTORS, default_embedding=UNRELATED
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
    gateway = fake_gateway("Select Forgot password on the sign-in page.")

    result = triage(PASSWORD_TICKET, gateway=gateway, settings=settings)

    assert result.decision == "auto_reply"
    assert "Select Forgot password on the sign-in page." in result.reply
    assert result.cited_article.id == "reset-password"
    assert result.cited_article.title == "Reset a staff member's password"
    assert "Reset a staff member's password" in result.reply


def test_weak_match_escalates_without_drafting_a_reply(settings):
    gateway = fake_gateway()  # no chat reply scripted: an escalation must not need one

    result = triage(FAX_TICKET, gateway=gateway, settings=settings)

    assert result.decision == "escalate"
    assert result.reply is None
    assert result.cited_article is None
    assert "retrieval_threshold" in result.escalation_reason


def read_trace(result) -> list[dict]:
    return [json.loads(line) for line in result.trace_path.read_text().splitlines()]


def test_auto_reply_run_writes_one_trace_record_per_step(settings):
    gateway = fake_gateway("Select Forgot password on the sign-in page.")

    result = triage(PASSWORD_TICKET, gateway=gateway, settings=settings)

    records = read_trace(result)
    assert [r["step"] for r in records] == ["retrieve", "threshold_check", "draft_reply"]
    for record in records:
        assert record["run_id"] == result.run_id
        assert record["input"] and record["output"]
        assert record["latency_ms"] >= 0
        assert set(record["tokens"]) == {"input", "output"}
    retrieve, threshold, draft = records
    assert retrieve["output"]["matches"][0]["article_id"] == "reset-password"
    assert threshold["decision"] == "pass"
    assert draft["decision"] == "auto_reply"
    assert draft["output"]["reply"] == result.reply
    assert draft["tokens"]["output"] == 7  # the fake counts words; the scripted reply has seven


def test_escalated_run_traces_the_failed_threshold_check(settings):
    result = triage(FAX_TICKET, gateway=fake_gateway(), settings=settings)

    records = read_trace(result)
    assert [r["step"] for r in records] == ["retrieve", "threshold_check"]
    assert records[-1]["decision"] == "escalate"
    assert records[-1]["output"]["reason"] == result.escalation_reason
