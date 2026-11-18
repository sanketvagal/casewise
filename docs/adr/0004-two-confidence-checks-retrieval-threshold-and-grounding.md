# 4. Two confidence checks before an auto-reply: retrieval threshold, then grounding

Date: 2026-11-17

Status: Accepted

## Context

An auto-reply is only safe when the knowledge base actually answers the ticket. Before this decision there was one confidence check: the best-matching article had to fall within a cosine-distance threshold.

Distance measures topical closeness, not whether the article answers the question. A ticket asking how to cancel a lab order embeds right next to an article on placing one, and "how do I cancel this appointment?" lands at 0.33 from the reschedule article (live, `all-MiniLM-L6-v2`), well inside the 0.5 threshold. Lowering the threshold far enough to reject these would also reject good matches.

Model output also needs a guarantee. The gateway returns plain text (ADR 1), and a step whose output can't be read must not be able to fail open.

## Decision

**Two independent checks, both required.** After the safety rules (ADR 3) pass:

1. `threshold_check`: the best article must be within `Settings.distance_threshold`. It is cheap, deterministic and needs no model call. Failing it escalates with `retrieval_threshold: ...`.
2. `grounding_check`: only if the threshold passed, the model is shown the ticket and the best article and returns a `GroundingVerdict` (`answers_ticket`, `reason`). `answers_ticket: false` escalates with `grounding_check: article '<id>' does not answer the ticket: <reason>`.

The threshold runs first, so a weak match never costs a grounding call, and the grounding check only has to separate right from wrong among articles that are already on topic.

**Every model step returns validated structured output.** Intent (`Intent`: label and confidence), grounding (`GroundingVerdict`), the auto-reply (`Draft`: reply and cited article id, which must be the article provided) and the review draft (`ReviewDraft`) are Pydantic models. The prompt asks for JSON matching the model's schema. The reply is parsed, tolerating a Markdown fence, and validated. On failure the step re-asks, sending back the rejected reply and the validation error, up to `Settings.structured_output_retries` times (default 2, so 3 attempts). Because a retry includes the error, it is a different prompt and so a different cache key (ADR 2): a cached bad reply can't be replayed forever.

**Exhausted retries escalate.** A step that never produces valid output escalates with `invalid_output:<step>: ...`. It is never treated as a pass. The one exception is the review draft, which runs only after the ticket is already escalated: its failure leaves a note in `suggested_draft` and changes nothing else.

**Escalation is one-way in the graph itself.** Triage is a LangGraph state graph. Its `escalation` field has a reducer that keeps the first value written, so no later node can clear or replace an escalation, whatever it returns. Once a ticket is escalated, routing skips every remaining decision step and goes to `draft_for_review`.

**Intent informs but does not decide.** Intent runs on every ticket, rule-escalated ones included, to fill `handoff.detected_intent` and the trace. It only affects routing when its output fails validation. Labels are the knowledge-base article ids plus `other` (`intent_labels()`), a placeholder until the topic taxonomy (issue 05) replaces it.

**Fixed sampling settings.** Chat calls stay at temperature 0. For `openai/gpt-oss-120b` on Groq, `reasoning_effort` is pinned to `medium` (Groq's documented default for gpt-oss, which accepts `low`, `medium` or `high`) and `include_reasoning` is false. `reasoning_format` is not sent, because Groq rejects it for gpt-oss. As ADR 2 says, these are fixed in code and are not in the cache key.

## Consequences

- An auto-reply now costs three chat calls (intent, grounding, draft) and an escalation two (intent, review draft), plus retries. The cache pays each once.
- The grounding check is itself a model judgment. A wrong "yes" still produces a wrong auto-reply; the threshold and the rules are the other layers. The ablation in issue 08 measures what each check contributes.
- A grounding "no" on an on-topic article is a strong knowledge-base-gap signal, and the handoff says so. The insights report (issue 10) can use these reasons.
- Validation is strict (unknown intent labels, wrong citations, empty text and out-of-range confidence are all rejected), which trades some escalations for never acting on malformed output.
- Temperature 0 goes against Groq's advice of 0.5 to 0.7 for reasoning models. Determinism and a stable cache matter more here. If quality suffers in the evaluation, revisit this and clear the cache.
- Provider JSON modes (Groq supports strict `json_schema` for gpt-oss-120b) would make malformed output rarer, but they would widen the gateway interface (ADR 1). Prompted JSON plus validation and retry works across providers. Revisit if retry rates in the evaluation are high.
