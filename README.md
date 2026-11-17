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
export GROQ_API_KEY=...
uv run casewise triage --subject "Can't log in" --body "How do I reset my password?"
```

Configuration is by environment variable; see `src/casewise/config.py`.
