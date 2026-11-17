"""The `casewise triage` command and configuration-driven gateway selection."""

import json

import pytest

from casewise import CachedGateway, ScriptedGateway, Settings, Ticket, build_gateway, triage
from casewise.cli import main


def test_cli_triages_a_ticket_from_the_cache_and_prints_the_result(tmp_path, monkeypatch, capsys):
    settings = Settings(trace_dir=tmp_path / "traces", cache_dir=tmp_path / "cache")
    provider = ScriptedGateway(
        chat_replies=["Use Forgot password."],
        embeddings={"password": [1.0, 0.0]},
        default_embedding=[0.0, 1.0],
    )
    ticket = Ticket(subject="Locked out", body="How do I reset my password?", plan_tier="pro")
    triage(ticket, gateway=CachedGateway(settings.cache_dir, provider=provider), settings=settings)
    monkeypatch.setenv("CASEWISE_GATEWAY_MODE", "replay")
    monkeypatch.setenv("CASEWISE_CACHE_DIR", str(settings.cache_dir))
    monkeypatch.setenv("CASEWISE_TRACE_DIR", str(settings.trace_dir))

    exit_code = main(
        ["triage", "--subject", "Locked out", "--body", "How do I reset my password?",
         "--plan-tier", "pro"]
    )  # fmt: skip

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["decision"] == "auto_reply"
    assert printed["cited_article"]["id"] == "reset-password"
    assert "Use Forgot password." in printed["reply"]


def test_cli_reads_a_ticket_from_a_json_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CASEWISE_GATEWAY_MODE", "replay")
    monkeypatch.setenv("CASEWISE_CACHE_DIR", str(tmp_path / "empty-cache"))
    monkeypatch.setenv("CASEWISE_TRACE_DIR", str(tmp_path / "traces"))
    ticket_file = tmp_path / "ticket.json"
    ticket_file.write_text(json.dumps({"subject": "Fax", "body": "Can you send faxes?"}))

    exit_code = main(["triage", "--ticket-file", str(ticket_file)])

    # Nothing is cached, so replay mode must refuse rather than reach for a live model.
    assert exit_code == 1
    assert "No cached" in capsys.readouterr().err


def test_provider_and_models_come_from_configuration():
    settings = Settings.from_env(
        {"CASEWISE_PROVIDER": "groq", "CASEWISE_CHAT_MODEL": "some-llama",
         "CASEWISE_DISTANCE_THRESHOLD": "0.3"}
    )  # fmt: skip

    assert settings.provider == "groq"
    assert settings.chat_model == "some-llama"
    assert settings.distance_threshold == 0.3


def test_an_unknown_provider_is_rejected_by_name():
    with pytest.raises(ValueError, match="'nope'.*groq"):
        build_gateway(Settings(provider="nope", gateway_mode="live"))


def test_an_unknown_gateway_mode_is_rejected():
    with pytest.raises(ValueError, match="live, record, replay"):
        build_gateway(Settings(gateway_mode="sometimes"))
