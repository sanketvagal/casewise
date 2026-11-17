# 01: Scaffold + first end-to-end triage

**What to build:** A brand-new `casewise` Python project where `casewise triage` takes one ticket, checks it against a tiny hand-written knowledge base (3 articles), and either auto-replies with a draft that cites its article or escalates because no article was a close enough match. Every run writes a trace. This is the tracer bullet: the thinnest path through the gateway, retrieval, the decision and the trace, which every later ticket builds on.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Git repository initialized; Python project managed with uv; ruff and pytest configured
- [ ] GitHub Actions workflow runs lint and tests on every push
- [ ] A model gateway interface covers chat completions and embeddings, with three implementations: real (Groq Llama for chat, Sentence Transformers for embeddings), cached replay (on-disk, keyed by model and prompt), and a scripted fake for tests
- [ ] The default provider is chosen by configuration
- [ ] Knowledge-base articles are embedded into a vector store (ChromaDB)
- [ ] `casewise triage` accepts a single ticket (subject, body, metadata) and returns either an auto-reply that cites its article or an escalation
- [ ] A best match beyond the cosine-distance threshold escalates
- [ ] Each run writes a JSONL trace with one record per step (input, output, latency, tokens, decision)
- [ ] Tests drive triage through its public entry point with the scripted fake gateway: one case for a close match that auto-replies, one for a weak match that escalates, and one checking the trace
- [ ] A cached-replay run returns the same result as the live run it was recorded from
- [ ] ADR written for the model gateway as the single substitution seam, and for the provider and cache design
