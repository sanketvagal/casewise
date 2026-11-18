# 03: Intent classification, grounding check, structured outputs

**What to build:** The triage graph gains an intent classification step and an LLM grounding check ("does this article actually answer this ticket?"). Every LLM step returns validated structured output and retries on malformed output. Grounding failures and repeated validation failures escalate. No LLM step can move a ticket away from escalation.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Triage runs as a LangGraph state graph: safety rules (or a placeholder for them) → intent → retrieval → threshold → grounding → draft or escalate
- [x] Every LLM step returns a validated Pydantic model (intent with confidence, grounding verdict with reason, draft with cited article)
- [x] Validation failures retry a set number of times, then escalate, never auto-reply
- [x] A grounding "no" escalates, with the reason recorded
- [x] Each trace record includes the intent and the grounding verdict
- [x] Tests: a close embedding match on the wrong question (placing vs cancelling a lab order) escalates when the grounding check says no
- [x] Tests: malformed output followed by valid output succeeds, and malformed output that keeps failing escalates
- [x] Tests: none of the LLM steps can turn an escalation into an auto-reply
- [x] ADR written for the two-check confidence design (retrieval threshold plus grounding)

## Comments

**2026-11-17 (agent):** Implemented test-first on branch `03-intent-grounding-structured-outputs`. Decisions and caveats:

- **Graph.** `triage()` builds a LangGraph `StateGraph`: `safety_rules -> intent -> retrieve -> threshold_check -> grounding_check -> draft_reply`, with every decision step routing to `draft_for_review` once the ticket is escalated. The state's `escalation` field has a keep-first reducer, so no node can clear an escalation (checked by mutation: making it last-write-wins fails 19 tests).
- **Structured output** lives in `src/casewise/structured.py`: the prompt asks for JSON matching the Pydantic schema, the reply is parsed (a Markdown fence is tolerated) and validated. A retry sends back the rejected reply and the validation error, so it is a new cache key, not a replay of the same bad answer. `Settings.structured_output_retries` (`CASEWISE_STRUCTURED_OUTPUT_RETRIES`) defaults to 2, so 3 attempts. Exhausted retries escalate as `invalid_output:<step>: ...`. The gateway interface is unchanged.
- **Intent representation.** Labels are the knowledge-base article ids plus `other`, built by `intent_labels()` in `triage.py`, the one place to swap in the issue 05 taxonomy. Validation rejects any other label. Intent informs the handoff and trace and does not route, except that invalid intent output escalates. A possible later check, escalating when the intent disagrees with the best article, was deliberately left out (ADR 4 is two checks).
- **Intent runs on rule-escalated tickets.** It fills `handoff.detected_intent`, which the spec's handoff packet asks for, and later gives intent macro-F1 over every ticket. It cannot decide anything: the escalation is already set and the reducer keeps it, and invalid intent output just leaves `detected_intent` empty. Cost: one extra chat call per escalation. Grounding does not run after a rule match or a threshold failure.
- **Draft citation is validated**: `Draft.cited_article_id` must equal the article provided, or the draft is retried.
- **Review-draft failure** does not change the decision; the handoff's `suggested_draft` says no draft could be produced.
- **Trace records** all carry top-level `intent` and `grounding`, as known when that step finished (`null` before), and model steps record `attempts` and `errors` in their output. `TriageResult` gained `intent` and `grounding`.
- **Test fake.** `ScriptedGateway(chat_replies={...})` now accepts replies keyed by step (`intent`, `grounding`, `draft`, `review_draft`), routed on the `Output:` line that `structured.output_instructions` writes into the prompt. Ordered lists still work. Builders are in `tests/replies.py`.
- **Groq settings.** `reasoning_effort="medium"` (pinned to Groq's documented gpt-oss default), `include_reasoning=False`, temperature 0, all fixed in `live.py`. `reasoning_format` is not sent because Groq rejects it for gpt-oss. Recorded in ADRs 2 and 4.
- **Live verification** on `openai/gpt-oss-120b`, record mode:
  - Password reset: auto-reply citing `reset-password` (intent `reset-password` 0.99, grounding yes).
  - Physician, prescription to the wrong pharmacy: escalated on `safety_rule:prescription_error` (intent `other`, no grounding call).
  - Fax integration: escalated on `retrieval_threshold`, best `download-invoice` at 0.771.
  - "How do I cancel her appointment completely so the slot opens up?": best match `reschedule-appointment` at 0.326, inside the threshold. The grounding check said no ("explains how to reschedule ... not how to cancel"), so it escalated on `grounding_check`.
  - No live call needed a retry.
  - Replaying all four with `CASEWISE_GATEWAY_MODE=replay` and an empty `GROQ_API_KEY` gave identical results.
- **Cache.** All earlier recordings were stale (prompts changed), so `cache/` was cleared and now holds only these four runs: 10 chat and 7 embedding entries.
- **Unverified or caveats:**
  - The retry path has not run against the real model, because none was needed.
  - Live intent was `other` for the wrong-pharmacy ticket and the appointment-cancel ticket. That is correct under the article-id labels, but it shows how coarse they are until issue 05.
  - Temperature 0 goes against Groq's 0.5-0.7 advice for reasoning models; kept for determinism (ADR 4).
