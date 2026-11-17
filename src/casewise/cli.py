"""The ``casewise`` command line."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from casewise.cache import CacheMiss
from casewise.config import Settings
from casewise.live import LiveDependencyMissing, build_gateway
from casewise.triage import Ticket, triage


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

    args = parser.parse_args(argv)
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
    except (CacheMiss, LiveDependencyMissing) as problem:
        print(f"casewise: {problem}", file=sys.stderr)
        return 1
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
