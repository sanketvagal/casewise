# 01: Scaffold + first end-to-end triage

**What to build:** A brand-new `casewise` Python project where `casewise triage` takes one ticket, checks it against a tiny hand-written knowledge base (3 articles), and either auto-replies with a draft that cites its article or escalates because no article was a close enough match. Every run writes a trace. This is the tracer bullet: the thinnest path through the gateway, retrieval, the decision and the trace, which every later ticket builds on.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] Git repository initialized; Python project managed with uv; ruff and pytest configured
- [x] GitHub Actions workflow runs lint and tests on every push
- [x] A model gateway interface covers chat completions and embeddings, with three implementations: real (`openai/gpt-oss-120b` on Groq for chat, Sentence Transformers for embeddings), cached replay (on-disk, keyed by model and prompt), and a scripted fake for tests
- [x] The default provider is chosen by configuration
- [x] Knowledge-base articles are embedded into a vector store (ChromaDB)
- [x] `casewise triage` accepts a single ticket (subject, body, metadata) and returns either an auto-reply that cites its article or an escalation
- [x] A best match beyond the cosine-distance threshold escalates
- [x] Each run writes a JSONL trace with one record per step (input, output, latency, tokens, decision)
- [x] Tests drive triage through its public entry point with the scripted fake gateway: one case for a close match that auto-replies, one for a weak match that escalates, and one checking the trace
- [x] A cached-replay run returns the same result as the live run it was recorded from
- [x] ADR written for the model gateway as the single substitution seam, and for the provider and cache design

## Comments

**2026-11-17 (agent):** Implemented test-first. Notes for whoever picks up 02 and 03:

- The cached-replay criterion is covered by a test where the scripted fake stands in for the live provider behind `CachedGateway`. No real Groq call has been made yet (no `GROQ_API_KEY` was available), so the Groq chat path in `LiveGateway` and the default model name `llama-3.3-70b-versatile` are unverified. The real Sentence Transformers embedder was run against the three articles.
- The live providers are an optional extra (`uv sync --extra live`) so CI and replay don't install torch.
- `distance_threshold` defaults to 0.5 as a placeholder. With `all-MiniLM-L6-v2`, on-topic sample tickets landed at 0.32-0.46 and off-topic ones at 0.75-0.79.
- Triage is a plain function for now; the LangGraph state graph arrives with 03.

**2026-11-17 (agent), later:** A live run with a real key got a 404 from Groq for `llama-3.3-70b-versatile`. Groq's deprecations page lists it as shut down on 2026-08-16 for free and developer tiers, with no Llama replacement; it recommends `openai/gpt-oss-120b`. The default `chat_model` is now `openai/gpt-oss-120b`, and the spec and issue 08 were updated to match.

**2026-11-17 (agent), verified:** A live run on `openai/gpt-oss-120b` auto-replied to a password-reset ticket and cited `reset-password`; an off-topic fax ticket escalated at distance 0.794. Replaying the recorded run with no API key (`CASEWISE_GATEWAY_MODE=replay`) returned the identical result. That recorded run is committed under `cache/`. The CLI now reads a `.env` from the working directory.
