"""Safety rules, driven through triage with the scripted fake gateway."""

import pytest

import replies as say
from casewise import ScriptedGateway, Settings, Ticket, triage
from paths import FIXTURE_KB

# Any ticket mentioning an appointment embeds right on top of the reschedule article,
# so without safety rules the fake gateway would happily auto-reply to it.
EMBEDDINGS = {
    "password": [1.0, 0.0, 0.0, 0.0],
    "appointment": [0.0, 1.0, 0.0, 0.0],
    "invoice": [0.0, 0.0, 1.0, 0.0],
}


@pytest.fixture
def settings(tmp_path):
    return Settings(trace_dir=tmp_path / "traces", cache_dir=tmp_path / "cache", kb_dir=FIXTURE_KB)


def willing_gateway() -> ScriptedGateway:
    """A model that would auto-reply from the reschedule article at every step."""
    return ScriptedGateway(
        chat_replies={
            "intent": say.intent("reschedule-appointment", confidence=0.99),
            "grounding": say.grounded(),
            "draft": say.draft("Open Schedule and choose Reschedule.", "reschedule-appointment"),
            "review_draft": say.review_draft("A colleague is looking into this."),
        },
        embeddings=EMBEDDINGS,
        default_embedding=[0.0, 0.0, 0.0, 1.0],
    )


def test_prescription_error_from_a_physician_escalates_even_when_the_model_would_auto_reply(
    settings,
):
    ticket = Ticket(
        subject="Wrong pharmacy",
        body="The prescription I sent after this morning's appointment went to the wrong "
        "pharmacy. How do I fix it?",
        requester_role="physician",
    )

    result = triage(ticket, gateway=willing_gateway(), settings=settings)

    assert result.decision == "escalate"
    assert result.reply is None
    assert result.cited_article is None
    assert result.escalation_reason.startswith("safety_rule:prescription_error")


FIRES = [
    (
        "patient_data_exposure",
        "front desk",
        "A new receptionist can open another patient's chart that she should not have access to.",
    ),
    ("prescription_error", "front desk", "A refill request went out with the wrong dosage."),
    ("billing_dispute", "biller", "We were charged twice this month and I want a refund."),
    (
        "suspected_outage",
        "practice admin",
        "The whole system is down. Nobody can log in at our practice.",
    ),
    (
        "urgent_clinician",
        "physician",
        "This is unacceptable. I need my appointment list fixed immediately.",
    ),
]

NEAR_MISSES = [
    # Mentions a patient, but nothing about their data.
    ("patient_data_exposure", "front desk", "How do I move a patient appointment to next week?"),
    # "subscription" is not a prescription.
    ("prescription_error", "practice admin", "Where do I see our subscription renewal date?"),
    # A routine billing question, not a dispute.
    ("billing_dispute", "biller", "Where can I download last month's invoice?"),
    # One person locked out is not an outage.
    ("suspected_outage", "front desk", "I forgot my password and can't sign in."),
    # A calm clinician.
    ("urgent_clinician", "physician", "How do I move an appointment to another day?"),
    # Urgent, but not from a clinician: role is an input to this rule.
    (
        "urgent_clinician",
        "front desk",
        "This is unacceptable. I need my appointment list fixed immediately.",
    ),
]


@pytest.mark.parametrize(("rule_id", "role", "body"), FIRES, ids=[f[0] for f in FIRES])
def test_rule_fires_on_a_representative_ticket(settings, rule_id, role, body):
    ticket = Ticket(subject="Help needed", body=body, requester_role=role)

    result = triage(ticket, gateway=willing_gateway(), settings=settings)

    assert result.decision == "escalate"
    assert result.escalation_reason.startswith(f"safety_rule:{rule_id}:")


@pytest.mark.parametrize(("rule_id", "role", "body"), NEAR_MISSES)
def test_rule_stays_silent_on_a_near_miss(settings, rule_id, role, body):
    # Only the rules are under test here. Near misses that match the password or invoice
    # article may still escalate on a later check, since the scripted draft cites the
    # reschedule article; what matters is that no safety rule is the reason.
    ticket = Ticket(subject="Help needed", body=body, requester_role=role)

    result = triage(ticket, gateway=willing_gateway(), settings=settings)

    assert "safety_rule" not in (result.escalation_reason or "")


def test_when_several_rules_match_the_reason_names_them_all(settings):
    ticket = Ticket(
        subject="Help needed",
        body="The system is down and a prescription went to the wrong pharmacy.",
        requester_role="front desk",
    )

    result = triage(ticket, gateway=willing_gateway(), settings=settings)

    assert result.escalation_reason.startswith("safety_rule:prescription_error:")
    assert "also matched: suspected_outage" in result.escalation_reason


def test_a_rule_added_to_the_rules_file_takes_effect_without_code_changes(settings, tmp_path):
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        """
rules:
  - id: legal_threat
    description: Legal threats always go to a human.
    phrases: [lawyer*, "legal action"]
    next_step: Loop in the account manager.
"""
    )
    custom = Settings(
        trace_dir=settings.trace_dir,
        cache_dir=settings.cache_dir,
        kb_dir=FIXTURE_KB,
        rules_path=rules_file,
    )
    ticket = Ticket(subject="Appointment sync", body="Fix this or you will hear from our lawyers.")

    result = triage(ticket, gateway=willing_gateway(), settings=custom)

    assert result.escalation_reason.startswith("safety_rule:legal_threat:")
    assert result.handoff.next_step == "Loop in the account manager."


def test_a_rules_file_with_a_repeated_id_is_rejected(settings, tmp_path):
    rules_file = tmp_path / "rules.yaml"
    rule = "  - {id: twin, description: d, phrases: [x], next_step: n}\n"
    rules_file.write_text("rules:\n" + rule + rule)
    custom = Settings(
        trace_dir=settings.trace_dir,
        cache_dir=settings.cache_dir,
        kb_dir=FIXTURE_KB,
        rules_path=rules_file,
    )

    with pytest.raises(ValueError, match="twin"):
        triage(Ticket(subject="s", body="b"), gateway=willing_gateway(), settings=custom)
