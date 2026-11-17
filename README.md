# casewise

> casewise: safety-first LLM triage for clinical SaaS support, with evals that prove it.

All data is synthetic. Work in progress.

## Quick start

```sh
uv sync                 # core + dev tools (no model weights, no API key needed)
uv run pytest           # tests use a scripted fake model gateway
uv run ruff check .

# Live triage needs the real providers and a Groq key
uv sync --extra live
cp .env.example .env    # then put your key in it (.env is gitignored)
uv run casewise triage --subject "Can't log in" --body "How do I reset my password?"
```

Tickets that match a rule in `safety_rules.yaml` always escalate to a human, before any model is consulted. Every escalation comes with a handoff packet: the reason, the closest articles, a suggested draft marked for human review, and a next step.

Configuration is by environment variable; see `src/casewise/config.py`.
