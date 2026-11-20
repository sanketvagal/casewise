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

Otherwise a ticket auto-replies only when two checks pass: the closest article is within a cosine-distance threshold, and a grounding check confirms that article actually answers the ticket. Every model step returns validated JSON; output that keeps failing validation escalates. See `docs/adr/0004-*`.

Configuration is by environment variable; see `src/casewise/config.py`.

## Evaluation

```sh
# Reproduce the recorded numbers from the committed cache: no API keys, no live extra
CASEWISE_GATEWAY_MODE=replay uv run casewise eval
```

`casewise eval` triages the labeled tickets in `eval/fixtures.jsonl`, has an LLM judge on a different model family (Gemini Flash-Lite; needs `GEMINI_API_KEY` when recording) grade each auto-reply against its labeled article, and writes `eval/results/latest.json` and `latest.md`. Deflection counts only correct auto-replies: a wrong answer is a failure, not a deflection. Definitions are in `GLOSSARY.md` and `docs/adr/0005-*`.

## Generated data

```sh
# Regenerate data/ from the committed cache: no API key needed
CASEWISE_GATEWAY_MODE=replay uv run casewise generate
```

All tickets and articles are synthetic, for a fictional, unbranded product. `casewise generate` builds them labels-first. A Gemini model (a different family from triage) writes a spec of 40 support topics. Code then picks 25 topics for the knowledge base and samples every ticket's labels before any text exists. After that, the model writes each ticket from its labels, and one article per covered topic. That gives 400 tickets, split by timestamp into weeks 1–2 and weeks 3–4. The 15 uncovered topics are the simulated gaps, recorded only in `data/scoring/` for scoring. `data/generation-report.md` shows how well the keyword safety rules match the generated text. See `docs/adr/0006-*`.
