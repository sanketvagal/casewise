"""Cached replay: a run recorded through the cache replays with no provider at all."""

import pytest

import replies as say
from casewise import CachedGateway, CacheMiss, ScriptedGateway, Settings, Ticket, triage
from paths import FIXTURE_KB

TOPIC_VECTORS = {"password": [1.0, 0.0, 0.0], "appointment": [0.0, 1.0, 0.0]}

TICKET = Ticket(subject="Locked out", body="How do I reset my password?")


@pytest.fixture
def settings(tmp_path):
    return Settings(trace_dir=tmp_path / "traces", cache_dir=tmp_path / "cache", kb_dir=FIXTURE_KB)


def record_run(settings):
    """Stand-in for a live run: the scripted fake plays the provider behind the cache."""
    provider = ScriptedGateway(
        chat_replies={
            "intent": say.intent("reset-password"),
            "grounding": say.grounded(),
            "draft": say.draft("Use Forgot password.", "reset-password"),
        },
        embeddings=TOPIC_VECTORS,
        default_embedding=[0.0, 0.0, 1.0],
    )
    recording = CachedGateway(settings.cache_dir, provider=provider)
    return triage(TICKET, gateway=recording, settings=settings)


def outcome(result):
    return result.model_dump(exclude={"run_id", "trace_path"})


def test_replay_returns_the_same_result_as_the_run_it_was_recorded_from(settings):
    recorded = record_run(settings)

    replayed = triage(TICKET, gateway=CachedGateway(settings.cache_dir), settings=settings)

    assert recorded.decision == "auto_reply"
    assert outcome(replayed) == outcome(recorded)


def test_replay_of_an_unrecorded_ticket_fails_instead_of_calling_a_provider(settings):
    record_run(settings)
    unseen = Ticket(subject="Calendar", body="How do I move an appointment?")

    with pytest.raises(CacheMiss):
        triage(unseen, gateway=CachedGateway(settings.cache_dir), settings=settings)


def test_cache_is_keyed_by_model(settings):
    record_run(settings)
    other_model = Settings(
        trace_dir=settings.trace_dir,
        cache_dir=settings.cache_dir,
        kb_dir=FIXTURE_KB,
        chat_model="another-model",
    )

    with pytest.raises(CacheMiss):
        triage(TICKET, gateway=CachedGateway(settings.cache_dir), settings=other_model)
