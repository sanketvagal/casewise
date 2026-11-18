"""`evaluate`: triage each labeled ticket, judge the auto-replies, score the run.

Triage and the judge each get their own scripted gateway, so a test controls what
triage decides and what the judge says independently.
"""

import json

import pytest

import replies as say
from casewise import ScriptedGateway, Settings, Ticket
from casewise.evaluate import LabeledTicket, evaluate

RESET_PASSWORD = (
    "# Reset a staff member's password\n\n"
    "Select **Forgot password** on the sign-in page and follow the email link.\n"
)
DOWNLOAD_INVOICE = "# Download an invoice\n\nOpen **Billing > Invoices** and select **Download**.\n"

EMBEDDINGS = {"password": [1.0, 0.0, 0.0], "invoice": [0.0, 1.0, 0.0]}
UNRELATED = [0.0, 0.0, 1.0]

PASSWORD_TICKET = Ticket(subject="Locked out", body="How do I reset my password?")


class Recording:
    """Wraps a gateway and remembers every chat call made through it."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def chat(self, model, messages):
        self.calls.append((model, [dict(m) for m in messages]))
        return self.inner.chat(model, messages)

    def embed(self, model, texts):
        return self.inner.embed(model, texts)


@pytest.fixture
def settings(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "reset-password.md").write_text(RESET_PASSWORD)
    (kb_dir / "download-invoice.md").write_text(DOWNLOAD_INVOICE)
    return Settings(
        trace_dir=tmp_path / "traces",
        cache_dir=tmp_path / "cache",
        kb_dir=kb_dir,
        judge_model="judge-model",
    )


def triage_gateway(**replies) -> ScriptedGateway:
    scripted = {
        "intent": say.intent("reset-password"),
        "grounding": say.grounded(),
        "draft": say.draft("Select Forgot password on the sign-in page.", "reset-password"),
        "review_draft": say.review_draft("A colleague is looking at this."),
    }
    scripted.update(replies)
    return ScriptedGateway(
        chat_replies=scripted, embeddings=EMBEDDINGS, default_embedding=UNRELATED
    )


def judge_says(*verdicts: str) -> Recording:
    return Recording(ScriptedGateway(chat_replies={"judge": list(verdicts)}))


def verdict(value: str, reason: str = "Matches the article.") -> str:
    return json.dumps({"verdict": value, "reason": reason})


def password_ticket(**labels) -> LabeledTicket:
    defaults = dict(
        id="pw", ticket=PASSWORD_TICKET, intent="reset-password",
        answering_article="reset-password", must_escalate=False,
    )  # fmt: skip
    return LabeledTicket(**{**defaults, **labels})


def test_the_judge_compares_the_reply_with_the_labeled_article_and_decides_correctness(settings):
    judge = judge_says(verdict("correct"))

    results = evaluate(
        [password_ticket()], gateway=triage_gateway(), judge_gateway=judge, settings=settings
    )

    [outcome] = results.outcomes
    assert outcome.decision == "auto_reply"
    assert outcome.judge == "correct"
    assert outcome.correct
    assert results.metrics.deflection_rate == 1.0
    [(model, messages)] = judge.calls
    assert model == "judge-model"
    prompt = "\n".join(m["content"] for m in messages)
    assert "Billing > Invoices" not in prompt
    assert "follow the email link" in prompt  # the labeled article's text
    assert "Select Forgot password on the sign-in page." in prompt  # the reply
    assert "How do I reset my password?" in prompt  # the ticket


def never_called() -> ScriptedGateway:
    """A judge with nothing scripted: any call to it fails the test."""
    return ScriptedGateway(chat_replies={})


def test_a_reply_citing_another_article_than_the_labeled_one_is_incorrect_without_judging(
    settings,
):
    # Triage answers from reset-password, but the label says download-invoice answers it.
    labeled = password_ticket(intent="download-invoice", answering_article="download-invoice")

    results = evaluate(
        [labeled], gateway=triage_gateway(), judge_gateway=never_called(), settings=settings
    )

    [outcome] = results.outcomes
    assert outcome.decision == "auto_reply"
    assert outcome.judge is None
    assert not outcome.correct
    assert results.metrics.answer_accuracy == 0.0


def test_an_auto_reply_on_a_must_escalate_ticket_is_unsafe_and_never_judged(settings):
    labeled = password_ticket(must_escalate=True, escalation_reason="urgent_clinician")

    results = evaluate(
        [labeled], gateway=triage_gateway(), judge_gateway=never_called(), settings=settings
    )

    [outcome] = results.outcomes
    assert outcome.judge is None
    assert results.metrics.unsafe_auto_replies == 1
    assert results.metrics.deflection_rate == 0.0


def test_an_incorrect_verdict_makes_the_reply_incorrect_and_keeps_the_judge_reason(settings):
    judge = judge_says(verdict("incorrect", "It invents a phone number to call."))

    results = evaluate(
        [password_ticket()], gateway=triage_gateway(), judge_gateway=judge, settings=settings
    )

    [outcome] = results.outcomes
    assert outcome.judge == "incorrect"
    assert outcome.judge_reason == "It invents a phone number to call."
    assert not outcome.correct


def test_a_judge_that_never_returns_a_valid_verdict_leaves_the_reply_unjudged_and_incorrect(
    settings,
):
    judge = judge_says("not json", '{"verdict": "maybe"}', "still not json")

    results = evaluate(
        [password_ticket()], gateway=triage_gateway(), judge_gateway=judge, settings=settings
    )

    [outcome] = results.outcomes
    assert len(judge.calls) == 3  # first try plus the default 2 retries
    assert outcome.judge == "unjudged"
    assert not outcome.correct
    assert results.metrics.unjudged == 1


def test_an_escalation_records_its_reason_and_detected_intent(settings):
    fax = LabeledTicket(
        id="fax", ticket=Ticket(subject="Fax", body="Can the system send faxes?"),
        intent="other", answering_article=None, must_escalate=True, escalation_reason="no_answer",
    )  # fmt: skip

    results = evaluate(
        [fax], gateway=triage_gateway(intent=say.intent("other")),
        judge_gateway=never_called(), settings=settings,
    )  # fmt: skip

    [outcome] = results.outcomes
    assert outcome.decision == "escalate"
    assert outcome.escalation_reason.startswith("retrieval_threshold:")
    assert outcome.predicted_intent == "other"
    assert outcome.escalation_reason_matches is True
    assert results.metrics.escalation_recall == 1.0
