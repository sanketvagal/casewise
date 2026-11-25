"""The `casewise eval` command: offline replay of a recorded run, and its output files."""

import importlib
import json
import re

import replies as say
from casewise import CachedGateway, ScriptedGateway, Settings
from casewise import evaluate as evaluate_module
from casewise.cli import main
from casewise.evaluate import LabeledTicket, evaluate, prompt_version
from paths import FIXTURE_KB

triage_module = importlib.import_module("casewise.triage")

LABELED = [
    {
        "id": "pw-1",
        "ticket": {"subject": "Locked out", "body": "How do I reset my password?"},
        "intent": "reset-password",
        "answering_article": "reset-password",
        "must_escalate": False,
    },
    {
        "id": "fax-1",
        "ticket": {"subject": "Fax", "body": "Can the system send faxes?"},
        "intent": "other",
        "answering_article": None,
        "must_escalate": True,
        "escalation_reason": "no_answer",
    },
]


def record_a_run(settings: Settings) -> None:
    """Fill the cache the way a live recording would, with scripted providers."""
    triage_provider = ScriptedGateway(
        chat_replies={
            "intent": [say.intent("reset-password"), say.intent("other")],
            "grounding": say.grounded(),
            "draft": say.draft("Use Forgot password.", "reset-password"),
            "review_draft": say.review_draft("A colleague is looking at this."),
        },
        embeddings={"password": [1.0, 0.0]},
        default_embedding=[0.0, 1.0],
    )
    judge_provider = ScriptedGateway(
        chat_replies={"judge": json.dumps({"verdict": "correct", "reason": "Matches."})}
    )
    evaluate(
        [LabeledTicket.model_validate(row) for row in LABELED],
        gateway=CachedGateway(settings.cache_dir, provider=triage_provider),
        judge_gateway=CachedGateway(settings.cache_dir, provider=judge_provider),
        settings=settings,
    )


def replay_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CASEWISE_GATEWAY_MODE", "replay")
    monkeypatch.setenv("CASEWISE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CASEWISE_KB_DIR", str(FIXTURE_KB))
    monkeypatch.setenv("CASEWISE_TRACE_DIR", str(tmp_path / "traces"))


def write_fixtures(tmp_path):
    path = tmp_path / "fixtures.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in LABELED))
    return path


def test_eval_replays_a_recorded_run_offline_and_writes_json_and_markdown_results(
    tmp_path, monkeypatch, capsys
):
    record_a_run(
        Settings(cache_dir=tmp_path / "cache", trace_dir=tmp_path / "traces", kb_dir=FIXTURE_KB)
    )
    replay_env(monkeypatch, tmp_path)
    out = tmp_path / "results"

    exit_code = main(["eval", "--fixtures", str(write_fixtures(tmp_path)), "--out", str(out)])

    assert exit_code == 0
    results = json.loads((out / "latest.json").read_text())
    assert results["metrics"]["deflection_rate"] == 0.5  # 1 correct auto-reply / 2 tickets
    assert results["metrics"]["answer_accuracy"] == 1.0
    assert results["metrics"]["unsafe_auto_replies"] == 0
    assert results["metrics"]["escalation_recall"] == 1.0
    assert [row["labeled"]["id"] for row in results["outcomes"]] == ["pw-1", "fax-1"]
    assert results["outcomes"][0]["correct"] is True
    summary = (out / "latest.md").read_text()
    assert "Deflection rate" in summary and "50.0%" in summary
    assert summary.strip() in capsys.readouterr().out


def test_eval_refuses_to_reach_a_live_model_on_a_cache_miss(tmp_path, monkeypatch, capsys):
    replay_env(monkeypatch, tmp_path)  # nothing recorded

    exit_code = main(
        ["eval", "--fixtures", str(write_fixtures(tmp_path)), "--out", str(tmp_path / "out")]
    )

    assert exit_code == 1
    assert "No cached" in capsys.readouterr().err
    assert not (tmp_path / "out" / "latest.json").exists()


def test_the_judge_has_its_own_provider_and_model_settings():
    settings = Settings.from_env(
        {"CASEWISE_JUDGE_PROVIDER": "groq", "CASEWISE_JUDGE_MODEL": "some-judge"}
    )

    assert settings.judge_provider == "groq"
    assert settings.judge_model == "some-judge"
    assert Settings().judge_provider != Settings().provider  # a different family by default


def test_every_eval_run_appends_a_record_to_the_results_history(tmp_path, monkeypatch):
    record_a_run(
        Settings(cache_dir=tmp_path / "cache", trace_dir=tmp_path / "traces", kb_dir=FIXTURE_KB)
    )
    replay_env(monkeypatch, tmp_path)
    fixtures, out = write_fixtures(tmp_path), tmp_path / "results"

    main(["eval", "--tickets", str(fixtures), "--out", str(out)])
    main(["eval", "--tickets", str(fixtures), "--out", str(out)])

    runs = [json.loads(line) for line in (out / "history.jsonl").read_text().splitlines()]
    assert len(runs) == 2
    run = runs[0]
    assert re.fullmatch(r"[0-9a-f]{40}", run["git_commit"])
    assert isinstance(run["git_dirty"], bool)
    assert run["prompt_version"] == prompt_version()
    assert run["chat_model"] == Settings().chat_model
    assert run["judge_model"] == Settings().judge_model
    assert run["distance_threshold"] == Settings().distance_threshold
    assert run["tickets"] == str(fixtures)
    assert run["metrics"]["deflection_rate"] == 0.5
    assert run["metrics"]["unsafe_auto_replies"] == 0


def test_the_prompt_version_changes_when_any_prompt_changes(monkeypatch):
    before = prompt_version()

    monkeypatch.setattr(triage_module, "GROUNDING_SYSTEM_PROMPT", "Be lenient.")
    after_triage_change = prompt_version()
    monkeypatch.setattr(evaluate_module, "JUDGE_SYSTEM_PROMPT", "Be lenient too.")

    assert after_triage_change != before
    assert prompt_version() not in (before, after_triage_change)
