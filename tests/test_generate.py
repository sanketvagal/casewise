"""Labels-first data generation, driven end to end through a scripted generator model."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from casewise import CachedGateway, ScriptedGateway, Settings
from casewise.cli import main
from casewise.evaluate import load_labeled_tickets
from casewise.generate import AREAS, REQUESTER_ROLES, GenerationError, generate
from casewise.kb import load_articles
from casewise.rules import load_rules

AREA_SIZES = {
    "scheduling": 7,
    "e-prescribing": 7,
    "lab-orders-results": 7,
    "billing": 7,
    "patient-portal": 6,
    "account-admin": 6,
}
RULE_IDS = [rule.id for rule in load_rules(Path("safety_rules.yaml"))]


def spec_reply(sizes: dict[str, int] = AREA_SIZES) -> str:
    topics = [
        {
            "id": f"{area}-topic-{i}",
            "area": area,
            "title": f"{area} topic {i}",
            "description": f"Customers ask how to do {area} task {i}.",
        }
        for area, count in sizes.items()
        for i in range(1, count + 1)
    ]
    return json.dumps({"summary": "Practice-management software for clinics.", "topics": topics})


def briefs(messages) -> list[dict]:
    """The ticket briefs a ticket-writing prompt asks for (its first user message)."""
    return json.loads(messages[1]["content"])["tickets"]


def echo_tickets(messages) -> str:
    return json.dumps(
        {
            "tickets": [
                {
                    "id": brief["id"],
                    "subject": f"Question about {brief['topic']}",
                    "body": f"A {brief['tone']}, {brief['detail']} note from the "
                    f"{brief['requester_role']} about {brief['topic']}.",
                }
                for brief in briefs(messages)
            ]
        }
    )


def echo_article(messages) -> str:
    topic = json.loads(messages[1]["content"])["topic"]
    return json.dumps({"title": topic["title"], "body": f"How to: {topic['description']}"})


def generator(ticket_texts=echo_tickets, spec=None) -> ScriptedGateway:
    return ScriptedGateway(
        chat_replies={
            "product_spec": spec or spec_reply(),
            "ticket_texts": ticket_texts,
            "kb_article": echo_article,
        }
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(cache_dir=tmp_path / "cache", trace_dir=tmp_path / "traces")


@pytest.fixture
def world(tmp_path: Path, settings: Settings):
    out = tmp_path / "data"
    generate(gateway=generator(), settings=settings, out_dir=out, seed=7)
    return out


def all_tickets(out: Path):
    return load_labeled_tickets(out / "tickets" / "weeks-1-2.jsonl") + load_labeled_tickets(
        out / "tickets" / "weeks-3-4.jsonl"
    )


def labels(out: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in (out / "labels.jsonl").read_text().splitlines()]
    return {row["id"]: row for row in rows}


def test_labels_are_on_disk_before_any_ticket_text_is_written(tmp_path, settings):
    out = tmp_path / "data"

    def write_only_from_recorded_labels(messages):
        recorded = labels(out)  # fails if the labels file is not written yet
        for brief in briefs(messages):
            assert brief["id"] in recorded
        return echo_tickets(messages)

    generate(
        gateway=generator(ticket_texts=write_only_from_recorded_labels),
        settings=settings,
        out_dir=out,
        seed=7,
    )


def test_each_ticket_is_written_from_its_own_labels(world):
    recorded = labels(world)
    spec = json.loads((world / "spec.json").read_text())
    titles = {topic["id"]: topic["title"] for topic in spec["topics"]}
    for labeled in all_tickets(world):
        label = recorded[labeled.id]
        assert labeled.topic == label["topic"]
        assert labeled.intent == label["intent"]
        assert labeled.must_escalate == label["must_escalate"]
        assert labeled.ticket.requester_role == label["requester_role"]
        # The scripted writer only sees the brief, so the text proves what the brief held.
        assert titles[label["topic"]] in labeled.ticket.subject
        assert f"{label['tone']}, {label['detail']}" in labeled.ticket.body


def test_knowledge_base_covers_only_the_intended_topics(world):
    spec = json.loads((world / "spec.json").read_text())
    topic_ids = {topic["id"] for topic in spec["topics"]}
    article_ids = {article.id for article in load_articles(world / "kb")}
    uncovered = set(json.loads((world / "scoring" / "uncovered-topics.json").read_text()))

    assert len(topic_ids) == 40
    assert len(article_ids) == 25
    assert article_ids | uncovered == topic_ids
    assert not article_ids & uncovered


def test_uncovered_topics_never_reach_triage_labels(world):
    uncovered = set(json.loads((world / "scoring" / "uncovered-topics.json").read_text()))
    tickets = all_tickets(world)
    on_gaps = [t for t in tickets if t.topic in uncovered]
    assert on_gaps, "the simulated gaps should have tickets"
    for labeled in on_gaps:
        assert labeled.intent == "other"
        assert labeled.answering_article is None
        assert labeled.must_escalate
        assert labeled.escalation_reason in {"no_answer", *RULE_IDS}
    for labeled in tickets:
        if labeled.topic not in uncovered:
            assert labeled.intent == labeled.topic == labeled.answering_article


def test_tickets_split_into_two_fortnights_by_timestamp(world):
    early = load_labeled_tickets(world / "tickets" / "weeks-1-2.jsonl")
    late = load_labeled_tickets(world / "tickets" / "weeks-3-4.jsonl")
    assert len(early) == len(late) == 200
    assert max(t.ticket.timestamp for t in early) < min(t.ticket.timestamp for t in late)
    first = min(t.ticket.timestamp for t in early)
    last = max(t.ticket.timestamp for t in late)
    assert (last - first).days < 28
    assert len({t.id for t in early + late}) == 400


def test_every_ticket_has_complete_metadata(world):
    for labeled in all_tickets(world):
        ticket = labeled.ticket
        assert ticket.subject.strip() and ticket.body.strip()
        assert ticket.requester_role in REQUESTER_ROLES
        assert ticket.practice_size and ticket.plan_tier
        assert isinstance(ticket.timestamp, datetime) and ticket.timestamp.tzinfo is not None


def test_a_share_of_tickets_is_must_escalate_for_each_safety_rule(world):
    tickets = all_tickets(world)
    by_rule = {rule: [t for t in tickets if t.escalation_reason == rule] for rule in RULE_IDS}
    assert all(by_rule.values()), "every safety rule should have tickets"
    assert 0.15 <= sum(map(len, by_rule.values())) / len(tickets) <= 0.25
    assert all(t.must_escalate for group in by_rule.values() for t in group)
    assert all(t.ticket.requester_role == "physician" for t in by_rule["urgent_clinician"])
    spec = json.loads((world / "spec.json").read_text())
    area = {topic["id"]: topic["area"] for topic in spec["topics"]}
    assert {area[t.topic] for t in by_rule["prescription_error"]} == {"e-prescribing"}
    assert {area[t.topic] for t in by_rule["billing_dispute"]} == {"billing"}


def test_tickets_vary_in_tone_and_detail(world):
    recorded = labels(world).values()
    assert len({label["tone"] for label in recorded}) >= 4
    assert {label["detail"] for label in recorded} == {"brief", "moderate", "detailed"}


def test_the_recorded_cache_regenerates_identical_files(tmp_path, settings):
    first, second = tmp_path / "first", tmp_path / "second"
    recording = CachedGateway(settings.cache_dir, provider=generator())
    generate(gateway=recording, settings=settings, out_dir=first, seed=7)
    generate(gateway=CachedGateway(settings.cache_dir), settings=settings, out_dir=second, seed=7)

    files = sorted(p.relative_to(first) for p in first.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(second) for p in second.rglob("*") if p.is_file())
    for path in files:
        assert (first / path).read_bytes() == (second / path).read_bytes(), path


def test_a_spec_that_misses_a_product_area_stops_generation(tmp_path, settings):
    no_billing = {area: n for area, n in AREA_SIZES.items() if area != "billing"} | {
        "scheduling": 14
    }
    with pytest.raises(GenerationError, match="product_spec"):
        generate(
            gateway=generator(spec=spec_reply(no_billing)),
            settings=settings,
            out_dir=tmp_path / "data",
            seed=7,
        )


def test_the_spec_names_every_product_area():
    assert set(AREA_SIZES) == set(AREAS)


def test_generate_command_exits_1_on_a_cache_miss_in_replay(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    Path("safety_rules.yaml").write_text(Path(__file__).parents[1].joinpath(
        "safety_rules.yaml").read_text())  # fmt: skip
    monkeypatch.setenv("CASEWISE_GATEWAY_MODE", "replay")

    assert main(["generate", "--out", "data"]) == 1
    assert "No cached chat call" in capsys.readouterr().err
