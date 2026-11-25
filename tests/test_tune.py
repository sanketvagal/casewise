"""Threshold tuning on weeks 1-2: the sweep, the choice, and the held-out guard."""

import json
import re
from dataclasses import replace
from datetime import UTC, datetime

import pytest

import replies as say
from casewise import ScriptedGateway, Settings
from casewise.cli import main
from casewise.evaluate import LabeledTicket, TicketOutcome
from casewise.triage import Ticket
from casewise.tune import (
    HELD_OUT_START,
    HeldOutTickets,
    at_threshold,
    choose_threshold,
    tune,
)
from paths import FIXTURE_KB, ROOT

WEEK_1 = "2026-10-06T09:00:00Z"
WEEK_3 = "2026-10-20T09:00:00Z"


def labeled(
    id: str,
    *,
    must_escalate: bool = False,
    answering_article: str | None = "reset-password",
    timestamp: str | None = WEEK_1,
    body: str = "How do I reset my password?",
) -> LabeledTicket:
    return LabeledTicket(
        id=id,
        ticket=Ticket(subject=id, body=body, timestamp=timestamp),
        intent=answering_article or "other",
        answering_article=answering_article,
        must_escalate=must_escalate,
        escalation_reason="no_answer" if must_escalate else None,
    )


def auto_reply(ticket: LabeledTicket, distance: float, *, judge: str = "correct"):
    return TicketOutcome(
        labeled=ticket,
        decision="auto_reply",
        cited_article="reset-password",
        predicted_intent="reset-password",
        judge=judge if not ticket.must_escalate else None,
        best_distance=distance,
    )


def escalation(ticket: LabeledTicket, distance: float, reason: str):
    return TicketOutcome(
        labeled=ticket,
        decision="escalate",
        escalation_reason=reason,
        predicted_intent="other",
        best_distance=distance,
    )


# --- The held-out guard -------------------------------------------------------------


def test_tuning_refuses_a_weeks_3_4_ticket_before_any_model_call(tmp_path):
    no_model = ScriptedGateway()  # raises if anything is asked of it
    tickets = [labeled("early"), labeled("late", timestamp=WEEK_3)]

    with pytest.raises(HeldOutTickets, match="late"):
        tune(tickets, gateway=no_model, judge_gateway=no_model, settings=_settings(tmp_path))


def test_tuning_refuses_a_ticket_with_no_timestamp(tmp_path):
    no_model = ScriptedGateway()

    with pytest.raises(HeldOutTickets, match="undated"):
        tune(
            [labeled("undated", timestamp=None)],
            gateway=no_model, judge_gateway=no_model, settings=_settings(tmp_path),
        )  # fmt: skip


def test_the_held_out_split_starts_where_the_generated_weeks_3_4_start():
    weeks_3_4 = (ROOT / "data" / "tickets" / "weeks-3-4.jsonl").read_text().splitlines()
    weeks_1_2 = (ROOT / "data" / "tickets" / "weeks-1-2.jsonl").read_text().splitlines()
    stamp = lambda line: datetime.fromisoformat(json.loads(line)["ticket"]["timestamp"])  # noqa: E731

    assert HELD_OUT_START == datetime(2026, 10, 19, tzinfo=UTC)
    assert all(stamp(line) >= HELD_OUT_START for line in weeks_3_4)
    assert all(stamp(line) < HELD_OUT_START for line in weeks_1_2)


def test_casewise_tune_exits_1_on_the_weeks_3_4_file_and_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("CASEWISE_GATEWAY_MODE", "replay")
    monkeypatch.setenv("CASEWISE_CACHE_DIR", str(tmp_path / "empty-cache"))
    monkeypatch.setenv("CASEWISE_TRACE_DIR", str(tmp_path / "traces"))
    out = tmp_path / "tuning"

    exit_code = main(
        ["tune", "--tickets", str(ROOT / "data" / "tickets" / "weeks-3-4.jsonl"),
         "--out", str(out)]
    )  # fmt: skip

    assert exit_code == 1
    assert "held out" in capsys.readouterr().err
    assert not out.exists()


# --- Scoring a threshold from the sweep run -------------------------------------------


def test_a_reply_beyond_the_threshold_becomes_a_retrieval_threshold_escalation():
    far = auto_reply(labeled("far"), 0.6)

    [outcome] = at_threshold([far], 0.5)

    assert outcome.decision == "escalate"
    assert outcome.escalation_reason.startswith("retrieval_threshold:")
    assert outcome.cited_article is None and outcome.judge is None
    assert outcome.correct is False


def test_escalations_decided_before_the_threshold_step_are_left_alone():
    rule = escalation(labeled("rule"), 0.9, "safety_rule:billing_dispute: d")
    bad_intent = escalation(labeled("intent"), 0.9, "invalid_output:intent: no valid output")
    near = auto_reply(labeled("near"), 0.2)

    assert at_threshold([rule, bad_intent, near], 0.5) == [rule, bad_intent, near]


def test_the_choice_is_the_highest_deflection_with_no_unsafe_auto_reply():
    outcomes = [
        auto_reply(labeled("a"), 0.30),
        auto_reply(labeled("unsafe", must_escalate=True, answering_article=None), 0.55),
        auto_reply(labeled("c"), 0.70),
    ]

    threshold, sweep = choose_threshold(outcomes)

    # 0.30-0.54 deflect 1/3 safely; from 0.55 the unsafe reply gets through.
    assert threshold == 0.30
    by_threshold = {point.threshold: point for point in sweep}
    assert by_threshold[0.29].deflection_rate == 0
    assert by_threshold[0.55].unsafe_auto_replies == 1
    assert by_threshold[0.70].deflection_rate == pytest.approx(2 / 3)


def test_ties_go_to_the_smaller_threshold():
    outcomes = [
        auto_reply(labeled("a"), 0.20),
        auto_reply(labeled("wrong"), 0.40, judge="incorrect"),
    ]

    threshold, _ = choose_threshold(outcomes)

    assert threshold == 0.20  # 0.40 adds only a wrong reply: same deflection, less accuracy


# --- The whole tuning run -------------------------------------------------------------


def cite_the_article_given(messages) -> str:
    article_id = re.search(r"Article id: (\S+)", messages[-1]["content"]).group(1)
    return say.draft("Here is how.", article_id)


def test_tuning_triages_without_a_cut_off_then_picks_a_threshold_that_stops_the_unsafe_reply(
    tmp_path,
):
    # The fax ticket sits 0.2 from the password article. Grounding wrongly passes it,
    # so any threshold of 0.2 or more lets an unsafe auto-reply through.
    gateway = ScriptedGateway(
        chat_replies={
            "intent": say.intent("reset-password"),
            "grounding": say.grounded(),
            "draft": cite_the_article_given,
            "review_draft": say.review_draft("A colleague will help."),
        },
        embeddings={
            "password": [1.0, 0.0, 0.0],
            "invoice": [0.0, 1.0, 0.0],
            "appointment": [0.0, 0.0, 1.0],
        },
        default_embedding=[0.8, 0.6, 0.0],
    )
    judge = ScriptedGateway(
        chat_replies={"judge": json.dumps({"verdict": "correct", "reason": "ok"})}
    )
    tickets = [
        labeled("pw"),
        labeled("fax", must_escalate=True, answering_article=None, body="Can it send a fax?"),
    ]

    # A configured threshold of 0.1 would cut the fax ticket off; the sweep must ignore it.
    settings = replace(_settings(tmp_path), distance_threshold=0.1)

    result = tune(tickets, gateway=gateway, judge_gateway=judge, settings=settings)

    sweep_decisions = {o.labeled.id: o.decision for o in result.sweep_run.outcomes}
    assert sweep_decisions == {"pw": "auto_reply", "fax": "auto_reply"}  # no cut-off
    assert result.threshold < 0.2
    chosen = {p.threshold: p for p in result.sweep}[result.threshold]
    assert chosen.deflection_rate == 0.5 and chosen.unsafe_auto_replies == 0


def test_the_default_threshold_is_the_one_committed_tuning_chose():
    committed = json.loads((ROOT / "eval" / "tuning" / "weeks-1-2.json").read_text())

    assert Settings().distance_threshold == committed["threshold"]


def _settings(tmp_path) -> Settings:
    return Settings(trace_dir=tmp_path / "traces", cache_dir=tmp_path / "cache", kb_dir=FIXTURE_KB)
