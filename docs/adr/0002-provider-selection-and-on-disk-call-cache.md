# 2. Provider chosen by configuration; model calls cached on disk by model and prompt

Date: 2026-11-17

Status: Accepted

## Context

ADR 1 puts every model call behind `ModelGateway`. This ADR records how the real implementation picks its provider and how calls are cached, so that an evaluation can be re-run for free, returns identical numbers, and works with no API key.

## Decision

**Provider selection.** `LiveGateway` looks its chat provider up by name in a registry (`CHAT_PROVIDERS`), and the name comes from configuration: `Settings.provider`, overridable with `CASEWISE_PROVIDER`. The default is `groq`. Model names are configuration too (`CASEWISE_CHAT_MODEL`, `CASEWISE_EMBEDDING_MODEL`). Embeddings always run locally with Sentence Transformers. Adding a provider (Gemini is planned) means adding one registry entry.

Provider SDKs and model weights are imported on first use and installed as an optional extra (`uv sync --extra live`). Tests, CI and cached replay never install or load them.

**Cache.** `CachedGateway` wraps an optional provider gateway:

- A hit is served from disk.
- A miss with a provider calls it and stores the answer (record mode).
- A miss without a provider raises `CacheMiss` (replay mode). Replay can never silently reach a live model.

`Settings.gateway_mode` (`CASEWISE_GATEWAY_MODE`) selects `live`, `record` or `replay`. The default is `record`.

The key is the model plus the prompt: for chat, the model name and the full message list; for embeddings, the model name and one text. Each entry is a JSON file named by the SHA-256 of its key, holding both key and value, under `cache/chat/` or `cache/embed/`. Embeddings are cached per text rather than per batch, so the knowledge base is embedded once however the calls are grouped.

Chat calls run at temperature 0. Sampling settings are fixed in code, not part of the key.

## Consequences

- A committed cache directory reproduces a run exactly, including token counts, so traces look the same under replay. Latency in a replayed trace is the replay's own, not the original call's.
- Any change to a prompt or model name is a cache miss. That is the intended behavior (a changed prompt is a new experiment) but it means prompt edits need a recording run with an API key before CI can replay them.
- One file per call is easy to diff and inspect, and merges cleanly, at the cost of many small files. If the full evaluation makes this unwieldy, the storage can change behind `CachedGateway` without touching callers.
- Because sampling settings are not in the key, changing them in code requires clearing the cache by hand. If they ever become configurable they must join the key.
- Stale entries are never evicted. Clearing the cache is a manual step.
