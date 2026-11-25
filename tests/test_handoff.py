"""Every escalation, whatever triggered it, comes with a complete handoff packet."""

import pytest

import replies as say
from casewise import ScriptedGateway, Settings, Ticket, triage
from paths import FIXTURE_KB

EMBEDDINGS = {
    "password": [1.0, 0.0, 0.0, 0.0],
    "appointment": [0.0, 1.0, 0.0, 0.0],
    "invoice": [0.0, 0.0, 1.0, 0.0],
}

ESCALATING_TICKETS = {
    "patient_data_exposure": Ticket(
        subject="Access", body="A temp can open another patient's chart.", requester_role="biller"
    ),
    "prescription_error": Ticket(
        subject="Rx", body="A prescription went to the wrong pharmacy.", requester_role="physician"
    ),
    "billing_dispute": Ticket(
        subject="Invoice", body="We were charged twice, please refund us.", requester_role="biller"
    ),
    "suspected_outage": Ticket(
        subject="Down", body="The system is down for everyone here.", requester_role="front desk"
    ),
    "urgent_clinician": Ticket(
        subject="Schedule",
        body="My appointment list is wrong and I need it fixed immediately.",
        requester_role="physician",
    ),
    "retrieval_threshold": Ticket(
        subject="Fax", body="Can the system send referral letters by fax?", requester_role="biller"
    ),
}


@pytest.fixture
def settings(tmp_path):
    return Settings(trace_dir=tmp_path / "traces", cache_dir=tmp_path / "cache", kb_dir=FIXTURE_KB)


def gateway() -> ScriptedGateway:
    return ScriptedGateway(
        chat_replies={
            "intent": say.intent("reschedule-appointment"),
            "grounding": say.grounded(),
            "draft": say.draft("Open Schedule and choose Reschedule.", "reschedule-appointment"),
            "review_draft": say.review_draft("Thanks for flagging this, we are looking into it."),
        },
        embeddings=EMBEDDINGS,
        default_embedding=[0.0, 0.0, 0.0, 1.0],
    )


@pytest.mark.parametrize("trigger", ESCALATING_TICKETS)
def test_every_escalation_includes_a_complete_handoff_packet(settings, trigger):
    result = triage(ESCALATING_TICKETS[trigger], gateway=gateway(), settings=settings)

    packet = result.handoff
    assert result.decision == "escalate"
    assert trigger in packet.reason
    assert packet.reason == result.escalation_reason
    assert [article.id for article in packet.top_articles] != []
    assert all(article.title and article.distance >= 0 for article in packet.top_articles)
    assert "FOR HUMAN REVIEW" in packet.suggested_draft
    assert "Thanks for flagging this, we are looking into it." in packet.suggested_draft
    assert packet.next_step.strip()
    assert packet.detected_intent == "reschedule-appointment"


def test_handoff_lists_the_closest_articles_best_first(settings):
    result = triage(ESCALATING_TICKETS["urgent_clinician"], gateway=gateway(), settings=settings)

    articles = result.handoff.top_articles
    assert articles[0].id == "reschedule-appointment"
    assert [a.distance for a in articles] == sorted(a.distance for a in articles)


def test_rule_escalation_takes_its_next_step_from_the_rule(settings):
    result = triage(ESCALATING_TICKETS["suspected_outage"], gateway=gateway(), settings=settings)

    assert "status page" in result.handoff.next_step
    assert result.handoff.triggered_rules == ["suspected_outage"]


def test_the_suggested_draft_is_never_returned_as_a_reply(settings):
    result = triage(ESCALATING_TICKETS["prescription_error"], gateway=gateway(), settings=settings)

    assert result.reply is None
    assert result.cited_article is None


def test_an_auto_reply_has_no_handoff_packet(settings):
    ticket = Ticket(subject="Calendar", body="How do I move an appointment to another day?")

    result = triage(ticket, gateway=gateway(), settings=settings)

    assert result.decision == "auto_reply"
    assert result.handoff is None
