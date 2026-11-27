"""The ``casewise`` command line."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from casewise.cache import CacheMiss
from casewise.config import Settings
from casewise.evaluate import (
    append_history,
    evaluate,
    load_labeled_tickets,
    run_record,
    summary_markdown,
    write_results,
)
from casewise.generate import DEFAULT_SEED, GenerationError, generate
from casewise.live import LiveUnavailable, build_gateway
from casewise.triage import Ticket, triage
from casewise.tune import HeldOutTickets, tune, write_tuning


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="casewise")
    commands = parser.add_subparsers(dest="command", required=True)

    triage_cmd = commands.add_parser(
        "triage", help="Triage one ticket: auto-reply with a cited draft, or escalate."
    )
    triage_cmd.add_argument("--ticket-file", type=Path, help="JSON file holding the ticket")
    triage_cmd.add_argument("--subject")
    triage_cmd.add_argument("--body")
    triage_cmd.add_argument("--requester-role")
    triage_cmd.add_argument("--practice-size")
    triage_cmd.add_argument("--plan-tier")
    triage_cmd.add_argument("--timestamp", help="ISO 8601")

    eval_cmd = commands.add_parser(
        "eval", help="Evaluate triage on labeled tickets and write the results."
    )
    eval_cmd.add_argument(
        "--tickets", "--fixtures", type=Path, default=Path("data/tickets/weeks-3-4.jsonl"),
        help="JSONL file of labeled tickets (default: the held-out weeks 3-4)",
    )  # fmt: skip
    eval_cmd.add_argument(
        "--out", type=Path, default=Path("eval/results"),
        help="Directory for latest.json, latest.md and the history.jsonl it appends to",
    )  # fmt: skip

    tune_cmd = commands.add_parser(
        "tune", help="Choose the retrieval distance threshold on weeks 1-2 tickets only."
    )
    tune_cmd.add_argument(
        "--tickets", type=Path, default=Path("data/tickets/weeks-1-2.jsonl"),
        help="JSONL file of weeks 1-2 labeled tickets; any later ticket is refused",
    )  # fmt: skip
    tune_cmd.add_argument(
        "--out", type=Path, default=Path("eval/tuning"),
        help="Directory for weeks-1-2.json and weeks-1-2.md",
    )  # fmt: skip

    generate_cmd = commands.add_parser(
        "generate", help="Generate the fictional clinic world: topics, labeled tickets, articles."
    )
    generate_cmd.add_argument(
        "--out", type=Path, default=Path("data"), help="Directory to write the world into"
    )
    generate_cmd.add_argument("--seed", type=int, default=DEFAULT_SEED)

    args = parser.parse_args(argv)
    # A .env in the working directory supplies API keys and CASEWISE_* settings.
    # Variables already set in the environment win.
    load_dotenv(Path.cwd() / ".env")
    if args.command == "eval":
        return _eval(args)
    if args.command == "generate":
        return _generate(args)
    if args.command == "tune":
        return _tune(args)
    return _triage(parser, args)


def _eval(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    labeled = load_labeled_tickets(args.tickets)
    try:
        results = evaluate(
            labeled,
            gateway=build_gateway(settings),
            judge_gateway=build_gateway(settings, provider=settings.judge_provider),
            settings=settings,
        )
    except (CacheMiss, LiveUnavailable) as problem:
        print(f"casewise: {problem}", file=sys.stderr)
        return 1
    # The record reads the git state before the results are written: eval/results/latest.*
    # are tracked, so rewriting them first would mark every run dirty.
    record = run_record(results, settings=settings, tickets=args.tickets)
    write_results(results, args.out)
    append_history(record, args.out)
    print(summary_markdown(results))
    return 0


def _tune(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    try:
        result = tune(
            load_labeled_tickets(args.tickets),
            gateway=build_gateway(settings),
            judge_gateway=build_gateway(settings, provider=settings.judge_provider),
            settings=settings,
        )
    except HeldOutTickets as problem:
        print(f"casewise: refusing to tune on held out tickets. {problem}", file=sys.stderr)
        return 1
    except (CacheMiss, LiveUnavailable) as problem:
        print(f"casewise: {problem}", file=sys.stderr)
        return 1
    write_tuning(result, args.out)
    print((args.out / "weeks-1-2.md").read_text(encoding="utf-8"))
    if result.threshold != settings.distance_threshold:
        print(
            f"The configured threshold is {settings.distance_threshold}. Set the default "
            f"distance_threshold in src/casewise/config.py to {result.threshold}."
        )
    return 0


def _generate(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    try:
        tickets = generate(
            gateway=build_gateway(settings, provider=settings.generator_provider),
            settings=settings,
            out_dir=args.out,
            seed=args.seed,
        )
    except (CacheMiss, LiveUnavailable, GenerationError) as problem:
        print(f"casewise: {problem}", file=sys.stderr)
        return 1
    print(f"Wrote {len(tickets)} labeled tickets to {args.out}")
    print((args.out / "generation-report.md").read_text(encoding="utf-8"))
    return 0


def _triage(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if args.ticket_file:
        ticket = Ticket.model_validate_json(args.ticket_file.read_text(encoding="utf-8"))
    elif args.subject and args.body:
        ticket = Ticket(
            subject=args.subject,
            body=args.body,
            requester_role=args.requester_role,
            practice_size=args.practice_size,
            plan_tier=args.plan_tier,
            timestamp=args.timestamp,
        )
    else:
        parser.error("triage needs --ticket-file, or both --subject and --body")

    settings = Settings.from_env()
    try:
        result = triage(ticket, gateway=build_gateway(settings), settings=settings)
    except (CacheMiss, LiveUnavailable) as problem:
        print(f"casewise: {problem}", file=sys.stderr)
        return 1
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
