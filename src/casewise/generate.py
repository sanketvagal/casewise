"""Labels-first generation of the fictional clinic world: topics, labels, tickets, articles.

The order is the point (ADR 6). A model writes the product spec (about 40 support
topics). Code then picks which topics the knowledge base covers and samples every
ticket's labels with a seeded random generator, and writes them to disk. Only then does
a model write each ticket's text from its labels, so the correct answer is known by
construction rather than read back from the text. The model is never told whether a
topic is covered.

Every model call goes through the gateway, so a recorded cache regenerates the same
files byte for byte.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from casewise import structured
from casewise.config import Settings
from casewise.evaluate import LabeledTicket
from casewise.gateway import ModelGateway
from casewise.kb import Article
from casewise.rules import Rule, load_rules, matching_rules
from casewise.triage import OTHER_INTENT, Ticket

DEFAULT_SEED = 5
TOPIC_COUNT = 40
COVERED_TOPICS = 25
TICKETS_PER_SPLIT = 200
RULE_SHARE = 0.2
"""Share of tickets in each split whose situation falls under a safety rule."""
BATCH_SIZE = 10
"""Tickets written per model call."""

AREAS: dict[str, str] = {
    "scheduling": "appointments, provider calendars, reminders, waitlists, recurring visits",
    "e-prescribing": (
        "sending prescriptions electronically, pharmacy directory, favorites and renewal "
        "requests, controlled-substance setup"
    ),
    "lab-orders-results": "placing lab orders, lab interfaces, receiving and reviewing results",
    "billing": (
        "claims, patient statements, payment posting, insurance eligibility, and the "
        "practice's own subscription invoices"
    ),
    "patient-portal": "patient accounts, secure messaging, online booking, forms, viewing results",
    "account-admin": "staff accounts, passwords, roles and permissions, practice settings",
}
"""The product areas every spec must cover. Ids are stable: labels refer to them."""
MIN_TOPICS_PER_AREA = 4

REQUESTER_ROLES = ("physician", "front desk", "biller", "practice admin")
ROLE_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "scheduling": (1, 6, 0.5, 2),
    "e-prescribing": (6, 1, 0, 1.5),
    "lab-orders-results": (4, 2, 0, 1.5),
    "billing": (0.5, 1.5, 6, 2.5),
    "patient-portal": (1, 4, 1, 2.5),
    "account-admin": (1, 2, 1, 5),
}
"""Who tends to write about each area, in ``REQUESTER_ROLES`` order."""
PRACTICE_SIZES = {
    "solo": "a solo practice (1 provider)",
    "small": "a small practice (2-5 providers)",
    "medium": "a medium practice (6-20 providers)",
    "large": "a large practice (more than 20 providers)",
}
PRACTICE_SIZE_WEIGHTS = (2, 4, 3, 1)
PLAN_TIERS = ("essentials", "professional", "enterprise")
PLAN_TIER_WEIGHTS = (4, 4, 2)
TONES = ("calm", "frustrated", "confused", "terse", "formal", "apologetic")
DETAILS = {
    "brief": "one or two sentences",
    "moderate": "three to five sentences",
    "detailed": (
        "a short paragraph or two with specifics, such as what they clicked, what they "
        "saw and what they already tried"
    ),
}
DETAIL_WEIGHTS = (3, 4, 3)

ROUTINE_SITUATION = (
    "A routine request: no patient information shown to the wrong person, no prescription "
    "that was sent wrongly or failed to send, no dispute about a charge, no sign of an "
    "outage, and no urgent clinical pressure."
)
RULE_SITUATIONS: dict[str, str] = {
    "patient_data_exposure": (
        "Patient information was, or may have been, visible to someone who should not "
        "see it, such as another patient, another practice or the wrong staff member. "
        "The requester is worried about it."
    ),
    "prescription_error": (
        "A prescription went wrong: it was sent with a mistake, went to the wrong "
        "pharmacy, failed to transmit, or shows the wrong medication or amount."
    ),
    "billing_dispute": (
        "The practice disagrees with what the product's company charged it, such as a "
        "duplicate or incorrect charge on its subscription, and wants the money back."
    ),
    "suspected_outage": (
        "The product, or part of it, seems to be down or failing for many people at "
        "once, and the practice cannot work normally."
    ),
    "urgent_clinician": (
        "The requester is a physician who is upset or under time pressure, with patients "
        "waiting, and needs the problem fixed straight away."
    ),
}
"""What a rule-labeled ticket is about, by safety rule id. Written as situations, not
as the rule's phrases: whether the keyword rules catch these tickets is a finding."""
RULE_AREAS: dict[str, set[str]] = {
    "prescription_error": {"e-prescribing"},
    "billing_dispute": {"billing"},
}
"""Rules whose tickets only make sense in some areas. Other rules can occur anywhere."""

WEEK_1_START = datetime(2026, 10, 5, tzinfo=UTC)
"""A Monday. Weeks 1-2 are the 14 days from here; weeks 3-4 the 14 after that."""
Split = Literal["weeks-1-2", "weeks-3-4"]
SPLITS: tuple[Split, Split] = ("weeks-1-2", "weeks-3-4")

_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class GenerationError(RuntimeError):
    """A generation step's output stayed invalid after every retry."""


class Topic(BaseModel):
    id: str = Field(description="Short kebab-case id, unique across all topics")
    area: str = Field(description="One of the product area ids")
    title: str = Field(description="What the customer wants to do, in the imperative")
    description: str = Field(description="One or two sentences: what customers ask, and why")

    @field_validator("id")
    @classmethod
    def _slug(cls, value: str) -> str:
        if not _SLUG.match(value) or len(value) > 60:
            raise ValueError("must be a short kebab-case id, like 'move-appointment'")
        return value

    @field_validator("area")
    @classmethod
    def _known_area(cls, value: str) -> str:
        if value not in AREAS:
            raise ValueError(f"must be one of: {', '.join(AREAS)}")
        return value


class ProductSpec(BaseModel):
    model_config = ConfigDict(title="product_spec", extra="forbid")

    summary: str = Field(description="Two or three sentences on what the product does")
    topics: list[Topic]

    @field_validator("topics")
    @classmethod
    def _covers_the_product(cls, topics: list[Topic], info: ValidationInfo) -> list[Topic]:
        expected = (info.context or {}).get("topic_count", TOPIC_COUNT)
        if not expected - 4 <= len(topics) <= expected + 4:
            raise ValueError(f"needs about {expected} topics, got {len(topics)}")
        ids = Counter(topic.id for topic in topics)
        if repeated := sorted(i for i, n in ids.items() if n > 1):
            raise ValueError(f"topic ids must be unique; repeated: {', '.join(repeated)}")
        per_area = Counter(topic.area for topic in topics)
        if thin := [area for area in AREAS if per_area[area] < MIN_TOPICS_PER_AREA]:
            raise ValueError(
                f"every area needs at least {MIN_TOPICS_PER_AREA} topics; too few in: "
                + ", ".join(thin)
            )
        return topics


class TicketLabel(BaseModel):
    """Everything known about a ticket before its text exists."""

    id: str
    split: Split
    timestamp: datetime
    topic: str
    area: str
    requester_role: str
    practice_size: str
    plan_tier: str
    tone: str
    detail: str
    safety_rule: str | None
    """The safety rule whose situation the ticket describes, if any."""
    intent: str
    answering_article: str | None
    must_escalate: bool
    escalation_reason: str | None


class WrittenTicket(BaseModel):
    id: str
    subject: str = Field(min_length=3)
    body: str = Field(min_length=10)


class TicketTexts(BaseModel):
    model_config = ConfigDict(title="ticket_texts", extra="forbid")

    tickets: list[WrittenTicket]

    @field_validator("tickets")
    @classmethod
    def _one_per_brief(cls, tickets: list[WrittenTicket], info: ValidationInfo):
        expected = (info.context or {}).get("ids")
        if expected is not None and sorted(t.id for t in tickets) != sorted(expected):
            raise ValueError(f"needs exactly one ticket for each brief id: {', '.join(expected)}")
        return tickets


class ArticleText(BaseModel):
    model_config = ConfigDict(title="kb_article", extra="forbid")

    title: str
    body: str = Field(description="The article body in Markdown, without the title")


SPEC_PROMPT = (
    "You design the support-topic map for a fictional clinical practice-management product "
    "used by outpatient clinics. It has no brand name: never name it, and never name a real "
    "company, product or person. List the topics customers most often contact support "
    "about, each a specific, distinct how-to question or problem (for example 'Move an "
    "appointment to another provider', not 'Scheduling'). Topics must not overlap. Cover "
    f"every product area below with at least {MIN_TOPICS_PER_AREA} topics.\n\n"
    "Product areas (id: scope):\n" + "\n".join(f"- {a}: {scope}" for a, scope in AREAS.items())
)
ARTICLE_PROMPT = (
    "You write knowledge-base articles for the support site of a fictional clinical "
    "practice-management product. It has no brand name: never name it, and never name a "
    "real company, product or person. Write one article that fully answers the topic for "
    "clinic staff: numbered steps with menu paths in bold (like **Settings > Staff**), the "
    "limits or conditions that apply, and what to do if it doesn't work. Invent plausible "
    "specifics and keep them consistent. The body is Markdown, 120 to 250 words, and does "
    "not repeat the title."
)
TICKET_PROMPT = (
    "You write realistic support tickets that clinic staff send to the support team of a "
    "fictional practice-management product. It has no brand name: never name it, and never "
    "name a real company, product or person. Write one ticket per brief. A ticket is a "
    "single email-style message with a subject and a body, in the requester's own voice, "
    "about the brief's topic, matching its situation, tone and level of detail:\n"
    + "\n".join(f"- {name}: {meaning}" for name, meaning in DETAILS.items())
    + "\nDescribe the problem the way a busy clinic employee would, not in the topic's "
    "words. Never mention the brief, topics, areas or situations. Never include a "
    "patient's real details: say 'a patient' or use made-up initials."
)


def generate(
    *,
    gateway: ModelGateway,
    settings: Settings,
    out_dir: Path,
    seed: int = DEFAULT_SEED,
) -> list[LabeledTicket]:
    """Generate the world into ``out_dir`` and return the labeled tickets.

    Writes ``spec.json``, ``scoring/uncovered-topics.json``, ``labels.jsonl``,
    ``tickets/weeks-1-2.jsonl``, ``tickets/weeks-3-4.jsonl``, ``kb/*.md`` and
    ``generation-report.md``. The labels file is written before any ticket text is.
    """
    out_dir = Path(out_dir)
    model = settings.generator_model
    retries = settings.structured_output_retries
    rules = load_rules(settings.rules_path)

    spec = _ask(
        gateway, model, SPEC_PROMPT, f"Write the product summary and exactly {TOPIC_COUNT} topics.",
        ProductSpec, retries, context={"topic_count": TOPIC_COUNT},
    )  # fmt: skip
    _write_json(out_dir / "spec.json", spec.model_dump())

    covered = choose_covered(spec, seed)
    uncovered = sorted(topic.id for topic in spec.topics if topic.id not in covered)
    _write_json(out_dir / "scoring" / "uncovered-topics.json", uncovered)

    labels = sample_labels(spec, covered, rules, seed)
    _write_jsonl(out_dir / "labels.jsonl", labels)

    tickets = write_tickets(labels, spec, gateway, model, retries)
    for split in SPLITS:
        _write_jsonl(
            out_dir / "tickets" / f"{split}.jsonl",
            [t for t, label in zip(tickets, labels, strict=True) if label.split == split],
        )

    articles = write_articles([t for t in spec.topics if t.id in covered], gateway, model, retries)
    kb_dir = out_dir / "kb"
    kb_dir.mkdir(parents=True, exist_ok=True)
    for stale in kb_dir.glob("*.md"):
        stale.unlink()
    for article in articles:
        (kb_dir / f"{article.id}.md").write_text(
            f"# {article.title}\n\n{article.body.strip()}\n", encoding="utf-8"
        )

    report = generation_report(labels, tickets, rules, spec, covered, seed=seed, model=model)
    (out_dir / "generation-report.md").write_text(report, encoding="utf-8")
    return tickets


def choose_covered(spec: ProductSpec, seed: int, count: int = COVERED_TOPICS) -> set[str]:
    """Pick the topics the initial knowledge base covers. The rest are simulated gaps."""
    ids = [topic.id for topic in spec.topics]
    return set(random.Random(f"{seed}:coverage").sample(ids, min(count, len(ids) - 1)))


def sample_labels(
    spec: ProductSpec,
    covered: set[str],
    rules: Sequence[Rule],
    seed: int,
    per_split: int = TICKETS_PER_SPLIT,
) -> list[TicketLabel]:
    """Sample every ticket's labels. No model is involved: the labels are the ground truth.

    Topic volume is uneven (a few topics get many tickets) and the same in both splits,
    so a gap that costs deflection in weeks 1-2 also costs it in weeks 3-4.
    """
    if missing := [rule.id for rule in rules if rule.id not in RULE_SITUATIONS]:
        raise ValueError(f"No ticket situation written for safety rule(s): {', '.join(missing)}")
    volume = random.Random(f"{seed}:volume")
    weights = {topic.id: volume.lognormvariate(0, 0.6) for topic in spec.topics}
    rng = random.Random(f"{seed}:labels")
    drafts: list[tuple[datetime, int, dict]] = []
    for split_index, split in enumerate(SPLITS):
        rule_count = round(per_split * RULE_SHARE)
        situations: list[Rule | None] = [rules[i % len(rules)] for i in range(rule_count)]
        situations += [None] * (per_split - rule_count)
        rng.shuffle(situations)
        for rule in situations:
            areas = RULE_AREAS.get(rule.id, set(AREAS)) if rule else set(AREAS)
            topics = [topic for topic in spec.topics if topic.area in areas]
            topic = rng.choices(topics, weights=[weights[t.id] for t in topics])[0]
            if rule and rule.requester_roles:
                role = rng.choice(sorted(rule.requester_roles))
            else:
                role = rng.choices(REQUESTER_ROLES, weights=ROLE_WEIGHTS[topic.area])[0]
            is_covered = topic.id in covered
            reason = rule.id if rule else (None if is_covered else "no_answer")
            draft = {
                "split": split,
                "topic": topic.id,
                "area": topic.area,
                "requester_role": role,
                "practice_size": rng.choices(list(PRACTICE_SIZES), PRACTICE_SIZE_WEIGHTS)[0],
                "plan_tier": rng.choices(PLAN_TIERS, PLAN_TIER_WEIGHTS)[0],
                "tone": rng.choice(TONES),
                "detail": rng.choices(list(DETAILS), DETAIL_WEIGHTS)[0],
                "safety_rule": rule.id if rule else None,
                "intent": topic.id if is_covered else OTHER_INTENT,
                "answering_article": topic.id if is_covered else None,
                "must_escalate": reason is not None,
                "escalation_reason": reason,
            }
            drafts.append((_business_hour(rng, split_index), len(drafts), draft))
    drafts.sort(key=lambda entry: entry[:2])
    return [
        TicketLabel(id=f"gen-{n:03d}", timestamp=timestamp, **draft)
        for n, (timestamp, _, draft) in enumerate(drafts, start=1)
    ]


def write_tickets(
    labels: Sequence[TicketLabel],
    spec: ProductSpec,
    gateway: ModelGateway,
    model: str,
    retries: int,
) -> list[LabeledTicket]:
    """Have the model write each ticket's text from its labels, in batches."""
    topics = {topic.id: topic for topic in spec.topics}
    written: dict[str, WrittenTicket] = {}
    for start in range(0, len(labels), BATCH_SIZE):
        batch = labels[start : start + BATCH_SIZE]
        briefs = [_brief(label, topics[label.topic]) for label in batch]
        texts = _ask(
            gateway, model, TICKET_PROMPT, json.dumps({"tickets": briefs}, indent=1),
            TicketTexts, retries, context={"ids": [label.id for label in batch]},
        )  # fmt: skip
        written.update({ticket.id: ticket for ticket in texts.tickets})
    return [_labeled(label, written[label.id]) for label in labels]


def write_articles(
    topics: Sequence[Topic], gateway: ModelGateway, model: str, retries: int
) -> list[Article]:
    """Have the model write one knowledge-base article per covered topic."""
    articles = []
    for topic in topics:
        text = _ask(
            gateway, model, ARTICLE_PROMPT,
            json.dumps({"topic": topic.model_dump()}, indent=1), ArticleText, retries,
        )  # fmt: skip
        articles.append(Article(id=topic.id, title=text.title.strip(), body=text.body))
    return articles


def generation_report(
    labels: Sequence[TicketLabel],
    tickets: Sequence[LabeledTicket],
    rules: Sequence[Rule],
    spec: ProductSpec,
    covered: set[str],
    *,
    seed: int,
    model: str,
) -> str:
    """Counts by split, and how well the keyword safety rules match the generated text.

    Names no uncovered topic: the report sits beside data that triage and insights read.
    """
    fired = {
        t.id: matching_rules(list(rules), f"{t.ticket.subject}\n\n{t.ticket.body}",
                             t.ticket.requester_role)
        for t in tickets
    }  # fmt: skip

    def count(split: str, test) -> int:
        return sum(1 for label in labels if label.split == split and test(label))

    rows = [
        ("Tickets", lambda _: True),
        ("Must-escalate", lambda label: label.must_escalate),
        ("  for a safety rule", lambda label: label.safety_rule is not None),
        ("  no answer (uncovered topic)", lambda label: label.escalation_reason == "no_answer"),
        ("Not must-escalate", lambda label: not label.must_escalate),
    ]
    lines = [
        "# Generation report",
        "",
        f"Seed {seed}. Ticket text, articles and topics written by `{model}`; labels "
        "sampled in code before any text. See ADR 6.",
        "",
        f"{len(spec.topics)} topics, {len(covered)} covered by the initial knowledge base.",
        "",
        "| | weeks 1-2 | weeks 3-4 |",
        "|---|---:|---:|",
        *(f"| {name} | {count(SPLITS[0], t)} | {count(SPLITS[1], t)} |" for name, t in rows),
        "",
        "## Do the keyword safety rules catch the rule-labeled tickets?",
        "",
        "Rule tickets were written from a situation, not from the rule's phrases.",
        "",
        "| Rule | Labeled | Caught by that rule | Caught by any rule |",
        "|---|---:|---:|---:|",
    ]
    for rule in rules:
        ids = [label.id for label in labels if label.safety_rule == rule.id]
        own = sum(1 for i in ids if any(m.rule.id == rule.id for m in fired[i]))
        any_rule = sum(1 for i in ids if fired[i])
        lines.append(f"| `{rule.id}` | {len(ids)} | {own} | {any_rule} |")
    routine = [label for label in labels if label.safety_rule is None]
    tripped = [label for label in routine if fired[label.id]]
    by_rule = Counter(fired[label.id][0].rule.id for label in tripped)
    lines += [
        "",
        "## Tickets with no rule situation that a rule fires on anyway",
        "",
        f"{len(tripped)} of {len(routine)}. Triage will escalate these: a cost to "
        "deflection, not a safety problem.",
        "",
    ]
    lines += [f"- `{rule_id}`: {n}" for rule_id, n in sorted(by_rule.items())]
    return "\n".join(lines).rstrip() + "\n"


def _brief(label: TicketLabel, topic: Topic) -> dict[str, str]:
    situation = RULE_SITUATIONS[label.safety_rule] if label.safety_rule else ROUTINE_SITUATION
    return {
        "id": label.id,
        "topic": topic.title,
        "what_customers_ask": topic.description,
        "requester_role": label.requester_role,
        "practice": PRACTICE_SIZES[label.practice_size],
        "plan_tier": label.plan_tier,
        "situation": situation,
        "tone": label.tone,
        "detail": label.detail,
    }


def _labeled(label: TicketLabel, text: WrittenTicket) -> LabeledTicket:
    return LabeledTicket(
        id=label.id,
        ticket=Ticket(
            subject=text.subject.strip(),
            body=text.body.strip(),
            requester_role=label.requester_role,
            practice_size=label.practice_size,
            plan_tier=label.plan_tier,
            timestamp=label.timestamp,
        ),
        topic=label.topic,
        intent=label.intent,
        answering_article=label.answering_article,
        must_escalate=label.must_escalate,
        escalation_reason=label.escalation_reason,
    )


def _business_hour(rng: random.Random, split_index: int) -> datetime:
    """A random weekday working-hours moment inside the split's fortnight."""
    first_day = WEEK_1_START + timedelta(days=14 * split_index)
    weekdays = [first_day + timedelta(days=d) for d in range(14)]
    day = rng.choice([d for d in weekdays if d.weekday() < 5])
    return day.replace(hour=rng.randint(7, 18), minute=rng.randrange(60))


def _ask[T: BaseModel](
    gateway: ModelGateway,
    model: str,
    system: str,
    user: str,
    output: type[T],
    retries: int,
    context: dict | None = None,
) -> T:
    messages = [
        {"role": "system", "content": f"{system}\n\n{structured.output_instructions(output)}"},
        {"role": "user", "content": user},
    ]
    reply = structured.ask(gateway, model, messages, output, retries=retries, context=context)
    if reply.value is None:
        title = output.model_config.get("title") or output.__name__
        raise GenerationError(
            f"{title} output failed validation after {reply.attempts} attempts: {reply.errors[-1]}"
        )
    return reply.value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8")
