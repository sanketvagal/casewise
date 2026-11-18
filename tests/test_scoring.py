"""Scoring an evaluation run: the metric definitions of ADR 5, on hand-built outcomes.

Every expected value is worked out by hand from the outcomes listed in each test.
"""

import pytest

from casewise import Ticket
from casewise.evaluate import LabeledTicket, TicketOutcome, score


def labeled(
    id: str,
    *,
    intent: str = "reset-password",
    answering_article: str | None = "reset-password",
    must_escalate: bool = False,
    escalation_reason: str | None = None,
) -> LabeledTicket:
    return LabeledTicket(
        id=id,
        ticket=Ticket(subject=f"Ticket {id}", body="..."),
        intent=intent,
        answering_article=answering_article,
        must_escalate=must_escalate,
        escalation_reason=escalation_reason,
    )


GOLD = object()
"""Predict the labeled intent (the default). Pass ``None`` for invalid intent output."""


def auto_reply(label: LabeledTicket, *, cited: str, judge: str | None, intent=GOLD):
    return TicketOutcome(
        labeled=label,
        decision="auto_reply",
        cited_article=cited,
        predicted_intent=label.intent if intent is GOLD else intent,
        judge=judge,
    )


def escalated(label: LabeledTicket, *, reason: str = "retrieval_threshold: ...", intent=GOLD):
    return TicketOutcome(
        labeled=label,
        decision="escalate",
        escalation_reason=reason,
        predicted_intent=label.intent if intent is GOLD else intent,
    )


def test_a_wrong_auto_reply_is_not_a_deflection():
    # 4 tickets: one correct auto-reply, one the judge rejects, two correct escalations.
    outcomes = [
        auto_reply(labeled("a"), cited="reset-password", judge="correct"),
        auto_reply(labeled("b"), cited="reset-password", judge="incorrect"),
        escalated(labeled("c", answering_article=None, must_escalate=True)),
        escalated(labeled("d", answering_article=None, must_escalate=True)),
    ]

    metrics = score(outcomes)

    assert metrics.deflection_rate == 0.25  # 1 correct auto-reply / 4 tickets
    assert metrics.answer_accuracy == 0.5  # 1 correct / 2 auto-replies
    assert metrics.unsafe_auto_replies == 0


def test_only_a_judged_correct_reply_citing_the_answering_article_on_a_safe_ticket_is_correct():
    rule_ticket = labeled("unsafe", must_escalate=True, escalation_reason="billing_dispute")
    outcomes = [
        auto_reply(labeled("ok"), cited="reset-password", judge="correct"),
        # On a must-escalate ticket: unsafe, and never correct, whatever the judge says.
        auto_reply(rule_ticket, cited="reset-password", judge="correct"),
        # Cites the wrong article: incorrect even with a passing verdict.
        auto_reply(labeled("wrong"), cited="download-invoice", judge="correct"),
        # The judge never produced a valid verdict: counts as incorrect.
        auto_reply(labeled("unjudged"), cited="reset-password", judge="unjudged"),
    ]

    metrics = score(outcomes)

    assert [o.correct for o in outcomes] == [True, False, False, False]
    assert metrics.unsafe_auto_replies == 1
    assert metrics.answer_accuracy == 0.25  # 1 / 4 auto-replies
    assert metrics.deflection_rate == 0.25  # 1 / 4 tickets
    assert metrics.unjudged == 1


def test_a_run_with_no_auto_replies_has_zero_accuracy_rather_than_failing():
    outcomes = [escalated(labeled("x", answering_article=None, must_escalate=True))]

    metrics = score(outcomes)

    assert metrics.auto_replies == 0
    assert metrics.answer_accuracy == 0.0
    assert metrics.deflection_rate == 0.0


def test_routing_is_scored_on_the_decision_against_must_escalate():
    must = dict(answering_article=None, must_escalate=True, escalation_reason="no_answer")
    outcomes = [
        auto_reply(labeled("a"), cited="reset-password", judge="correct"),
        # A wrong reply is still a correct routing decision: correctness is separate.
        auto_reply(labeled("b"), cited="reset-password", judge="incorrect"),
        escalated(labeled("c")),  # should have auto-replied
        escalated(labeled("h")),  # should have auto-replied
        escalated(labeled("d", **must)),
        escalated(labeled("e", **must)),
        escalated(labeled("g", **must), reason="grounding_check: ..."),
        auto_reply(labeled("f", **must), cited="reset-password", judge=None),  # unsafe
    ]

    metrics = score(outcomes)

    # Rows are the label (must-escalate or not), columns the decision.
    assert metrics.confusion == {
        "auto_reply": {"auto_reply": 2, "escalate": 2},
        "escalate": {"auto_reply": 1, "escalate": 3},
    }
    # auto_reply: 2 right of 3 predicted, 2 found of 4 actual.
    # escalate:   3 right of 5 predicted, 3 found of 4 actual.
    assert metrics.precision == {"auto_reply": 2 / 3, "escalate": 3 / 5}
    assert metrics.recall == {"auto_reply": 2 / 4, "escalate": 3 / 4}
    assert metrics.escalation_recall == 3 / 4


def test_intent_macro_f1_averages_the_gold_classes_and_counts_invalid_output_as_wrong():
    cases = [  # (gold intent, predicted intent)
        ("reset-password", "reset-password"),
        ("reset-password", "reset-password"),
        ("reset-password", "download-invoice"),
        ("download-invoice", "download-invoice"),
        ("other", "other"),
        ("other", None),  # invalid intent output
        ("other", "reschedule-appointment"),  # predicted class absent from the gold labels
    ]
    outcomes = [
        escalated(labeled(str(i), intent=gold), intent=predicted)
        for i, (gold, predicted) in enumerate(cases)
    ]

    metrics = score(outcomes)

    # reset-password:   P = 2/2, R = 2/3 -> F1 = 0.8
    # download-invoice: P = 1/2, R = 1/1 -> F1 = 2/3
    # other:            P = 1/1, R = 1/3 -> F1 = 0.5
    assert metrics.intent_macro_f1 == pytest.approx((0.8 + 2 / 3 + 0.5) / 3)


def test_escalation_reason_agreement_is_reported_over_escalated_must_escalate_tickets():
    def must(id, expected):
        return labeled(id, answering_article=None, must_escalate=True, escalation_reason=expected)

    outcomes = [
        escalated(must("d", "no_answer"), reason="retrieval_threshold: best match ..."),
        escalated(must("e", "billing_dispute"), reason="safety_rule:billing_dispute: Billing ..."),
        # Escalated for a different reason than labeled: a correct escalation that
        # still disagrees on the reason.
        escalated(must("g", "prescription_error"), reason="retrieval_threshold: ..."),
        escalated(must("h", "no_answer"), reason="invalid_output:intent: no valid output ..."),
        # Not counted: an auto-reply on a must-escalate ticket, and a needless escalation.
        auto_reply(must("f", "no_answer"), cited="reset-password", judge=None),
        escalated(labeled("c")),
    ]

    metrics = score(outcomes)

    assert [o.escalation_reason_matches for o in outcomes] == [
        True, True, False, False, None, None
    ]  # fmt: skip
    assert metrics.escalation_reason_agreement == 0.5  # 2 of 4
    # The disagreeing tickets still count as escalations; only f was missed: 4 of 5.
    assert metrics.escalation_recall == 0.8
