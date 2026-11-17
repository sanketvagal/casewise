"""The grounding check, retries on malformed model output, and one-way escalation."""

import pytest

import replies as say
from casewise import ScriptedGateway, Settings, Ticket, triage

# Anything mentioning a lab order lands right on top of the lab-order article.
EMBEDDINGS = {
    "lab order": [1.0, 0.0, 0.0],
    "password": [0.0, 1.0, 0.0],
}
UNRELATED = [0.0, 0.0, 1.0]

PLACE_LAB_ORDER = """# Place a lab order

Clinicians can send a lab order to a connected lab from a patient's visit.

1. Open the visit and select **Orders > New lab order**.
2. Choose the lab and the tests, then select **Send**.
"""

CANCEL_TICKET = Ticket(
    subject="Lab order sent by mistake",
    body="I sent a lab order to the wrong lab. How do I cancel the lab order?",
    requester_role="front desk",
)
PLACE_TICKET = Ticket(subject="New lab order", body="How do I send a lab order to the lab we use?")


@pytest.fixture
def settings(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "place-lab-order.md").write_text(PLACE_LAB_ORDER)
    (kb_dir / "reset-password.md").write_text(
        "# Reset a staff member's password\n\nSelect **Forgot password** on the sign-in page.\n"
    )
    return Settings(trace_dir=tmp_path / "traces", cache_dir=tmp_path / "cache", kb_dir=kb_dir)


def gateway(**replies) -> ScriptedGateway:
    scripted = {
        "intent": say.intent("place-lab-order"),
        "grounding": say.grounded(),
        "draft": say.draft("Open the visit and choose Orders > New lab order.", "place-lab-order"),
        "review_draft": say.review_draft("Thanks, a colleague is looking at this."),
    }
    scripted.update(replies)
    return ScriptedGateway(
        chat_replies=scripted, embeddings=EMBEDDINGS, default_embedding=UNRELATED
    )


def test_a_grounded_close_match_auto_replies(settings):
    result = triage(PLACE_TICKET, gateway=gateway(), settings=settings)

    assert result.decision == "auto_reply"
    assert result.cited_article.id == "place-lab-order"


def test_close_match_on_the_wrong_question_escalates_when_grounding_says_no(settings):
    reason = "The article covers placing a lab order; the ticket asks how to cancel one."
    model = gateway(grounding=say.not_grounded(reason))

    result = triage(CANCEL_TICKET, gateway=model, settings=settings)

    assert result.decision == "escalate"
    assert result.reply is None
    assert result.cited_article is None
    assert result.escalation_reason.startswith("grounding_check:")
    assert "place-lab-order" in result.escalation_reason
    assert reason in result.escalation_reason
    assert result.grounding.answers_ticket is False
    assert result.handoff.reason == result.escalation_reason
    assert result.handoff.top_articles[0].id == "place-lab-order"
    assert result.handoff.top_articles[0].distance == pytest.approx(0.0, abs=1e-6)
    assert result.handoff.detected_intent == "place-lab-order"
    assert "knowledge-base gap" in result.handoff.next_step
    # The article does not answer the ticket, so the suggested draft must not cite it.
    assert "Source:" not in result.handoff.suggested_draft


MALFORMED = {
    "intent": [
        "Sure! The intent is place-lab-order.",  # not JSON
        say.intent("lab-cancellation"),  # not one of the labels
        '{"intent": "place-lab-order", "confidence": 7}',  # confidence out of range
    ],
    "grounding": [
        "yes",
        '{"answers_ticket": "probably", "reason": "close enough"}',
        '{"answers_ticket": true}',  # no reason
    ],
    "draft": [
        "Open the visit and choose Orders.",  # prose, not JSON
        say.draft("Open the visit and choose Orders.", "reset-password"),  # cites the wrong article
        '{"reply": "", "cited_article_id": "place-lab-order"}',  # empty reply
    ],
}
VALID = {
    "intent": say.intent("place-lab-order"),
    "grounding": say.grounded(),
    "draft": say.draft("Open the visit and choose Orders > New lab order.", "place-lab-order"),
}


@pytest.mark.parametrize("step", MALFORMED)
def test_malformed_output_followed_by_valid_output_succeeds(settings, step):
    model = gateway(**{step: [MALFORMED[step][0], VALID[step]]})

    result = triage(PLACE_TICKET, gateway=model, settings=settings)

    assert result.decision == "auto_reply"
    assert result.cited_article.id == "place-lab-order"
    assert result.intent.intent == "place-lab-order"


@pytest.mark.parametrize("step", MALFORMED)
def test_output_that_keeps_failing_validation_escalates(settings, step):
    # Two retries are allowed by default: three bad replies use them all up, and the
    # valid fourth reply must never be asked for.
    model = gateway(**{step: [*MALFORMED[step], VALID[step]]})

    result = triage(PLACE_TICKET, gateway=model, settings=settings)

    assert result.decision == "escalate"
    assert result.reply is None
    assert result.escalation_reason.startswith("invalid_output:")
    assert "after 3 attempts" in result.escalation_reason
    assert result.handoff.next_step.strip()
    assert "FOR HUMAN REVIEW" in result.handoff.suggested_draft


def test_the_number_of_retries_is_a_setting(tmp_path, settings):
    no_retries = Settings(
        trace_dir=settings.trace_dir, cache_dir=settings.cache_dir, kb_dir=settings.kb_dir,
        structured_output_retries=0,
    )  # fmt: skip
    model = gateway(grounding=[MALFORMED["grounding"][0], VALID["grounding"]])

    result = triage(PLACE_TICKET, gateway=model, settings=no_retries)

    assert result.decision == "escalate"
    assert "after 1 attempts" in result.escalation_reason


def test_retry_count_comes_from_configuration():
    assert (
        Settings.from_env({"CASEWISE_STRUCTURED_OUTPUT_RETRIES": "5"}).structured_output_retries
        == 5
    )


def test_a_review_draft_that_keeps_failing_still_yields_a_complete_handoff(settings):
    model = gateway(grounding=say.not_grounded("Wrong question."), review_draft="not json")

    result = triage(CANCEL_TICKET, gateway=model, settings=settings)

    assert result.decision == "escalate"
    assert result.escalation_reason.startswith("grounding_check:")
    assert result.handoff.suggested_draft.startswith("[FOR HUMAN REVIEW")
    assert "failed validation" in result.handoff.suggested_draft


# --- No model step can turn an escalation into an auto-reply -------------------------

RULE_TICKET = Ticket(
    subject="Lab order for a prescription",
    body="How do I send a lab order with the prescription for this patient?",
    requester_role="physician",
)
FAR_TICKET = Ticket(subject="Fax", body="Can the system fax referral letters?")

ESCALATIONS = {
    "safety_rule": (RULE_TICKET, {}),
    "retrieval_threshold": (FAR_TICKET, {"intent": say.intent("other")}),
    "grounding_check": (CANCEL_TICKET, {"grounding": say.not_grounded("Wrong question.")}),
    "invalid_output": (PLACE_TICKET, {"intent": "I cannot classify this."}),
}


@pytest.mark.parametrize("source", ESCALATIONS)
def test_no_model_step_turns_an_escalation_into_an_auto_reply(settings, source):
    """Every other model reply is as willing as possible: a confident intent, a grounding
    "yes" and a valid draft citing the closest article. The escalation still stands."""
    ticket, overrides = ESCALATIONS[source]

    result = triage(ticket, gateway=gateway(**overrides), settings=settings)

    assert result.decision == "escalate"
    assert result.reply is None
    assert result.cited_article is None
    assert result.escalation_reason.startswith(source)
    assert result.handoff.reason == result.escalation_reason


def test_after_a_rule_match_no_model_step_makes_a_decision(settings):
    # The intent output is garbage and the grounding check would say yes, but the rule
    # match is the reason, and grounding never runs.
    model = gateway(intent=["nonsense", "nonsense", "nonsense"])

    result = triage(RULE_TICKET, gateway=model, settings=settings)

    assert result.decision == "escalate"
    assert result.escalation_reason.startswith("safety_rule:prescription_error:")
    assert result.grounding is None
    assert result.handoff.detected_intent is None


def test_a_rule_escalated_ticket_still_gets_its_intent_for_the_handoff(settings):
    result = triage(RULE_TICKET, gateway=gateway(), settings=settings)

    assert result.escalation_reason.startswith("safety_rule:prescription_error:")
    assert result.handoff.detected_intent == "place-lab-order"
