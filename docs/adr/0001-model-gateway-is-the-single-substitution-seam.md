# 1. The model gateway is the single substitution seam

Date: 2026-11-17

Status: Accepted

## Context

casewise makes two kinds of model call: chat completions and embeddings. Three needs pull on how those calls are made:

- Tests must be fast, deterministic and free, yet exercise real behavior.
- A reviewer must reproduce every reported number from a fresh clone with no API key.
- The provider must be swappable for the model comparison and to avoid lock-in.

If each of these were solved at a different place (mocked retrieval here, a patched SDK there, a stubbed pipeline step elsewhere), the tests would stop describing the system that runs in production.

## Decision

Every chat completion and every embedding goes through one interface, `ModelGateway`, with two methods:

- `chat(model, messages) -> ChatResult` (text plus input and output token counts)
- `embed(model, texts) -> list[list[float]]`

It is the only thing ever substituted. It has three implementations:

- `LiveGateway`: a real chat provider plus Sentence Transformers embeddings.
- `CachedGateway`: on-disk replay, optionally recording from another gateway (see ADR 2).
- `ScriptedGateway`: a fake for tests, with chat replies and embedding vectors set per test.

The public entry points (`triage`, later `evaluate` and `insights`) take the gateway as an argument. Nothing else is injected or mocked: the knowledge base, ChromaDB, thresholds and trace writing always run for real.

The caller passes the model name on every call. The gateway holds no model state, which is what lets the cache key on model and prompt alone.

## Consequences

- Tests drive the public entry points and script only what a model would say. They survive internal refactors, including the planned move to a LangGraph state graph.
- Code must not import a provider SDK or an embedding library outside the `LiveGateway` module. A model call that bypasses the gateway breaks caching, replay and the tests at once.
- Embeddings are behind the gateway too, so tests control retrieval distance by scripting vectors while the vector store itself stays real.
- The interface is deliberately small. Provider features that don't fit (streaming, native tool calls, provider-side JSON modes) are unavailable until the interface is widened, and widening it means updating all three implementations.
