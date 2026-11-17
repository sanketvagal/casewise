# 3. Safety rules run first; the LLM can only add escalations, never remove them

Date: 2026-11-17

Status: Accepted

## Context

casewise serves a clinical product. Some tickets must reach a human however confident a model is: patient-data access or exposure, prescriptions and e-prescribing problems, billing disputes, suspected outages, and upset or urgent clinicians. The headline safety metric is unsafe auto-replies, with a target of zero.

A model asked "is this safe to auto-reply?" will sometimes say yes when it should not, and a prompt change can shift that silently. A support lead also needs to audit and adjust what always escalates without reading code or prompts.

## Decision

**Rules are deterministic and run first.** `safety_rules.yaml` at the repo root lists the rules. Each has a stable `id`, a one-sentence `description`, the `phrases` that trigger it, an optional `requester_roles` restriction, and a `next_step` for the agent. Matching is plain text: case-insensitive, whole words, with a trailing `*` for word prefixes. Triage evaluates every rule against the ticket's subject and body before any model call.

**A rule match is final.** Once a rule matches, the decision is "escalate". Triage does not run the retrieval-threshold check as a decision, and it never takes the auto-reply path. The escalation reason is `safety_rule:<id>: <description>`, listing any further rules that also matched.

**Model steps are one-directional.** Every later check, today the retrieval threshold and from issue 03 the intent and grounding steps, can turn a would-be auto-reply into an escalation. None can turn an escalation into an auto-reply. An auto-reply needs every check to pass; an escalation needs only one to fail.

**The model still helps after an escalation, without deciding anything.** Intent classification, retrieval and one more chat call run to fill the handoff packet: the detected intent, the top articles and a suggested draft. Intent output that fails validation leaves `detected_intent` empty and does not change the reason. The draft is prefixed `[FOR HUMAN REVIEW: ...]` and lives only in `handoff.suggested_draft`. `reply` and `cited_article` stay empty on every escalation.

## Consequences

- Unsafe auto-replies on rule-covered tickets depend on the rules file, not on model behavior. The ablation that turns rules off (issue 08) measures what they contribute.
- Phrase matching is blunt. It over-escalates ("chart" in a harmless how-to question) and misses phrasings nobody listed. Over-escalation costs deflection, which is the accepted trade. Misses are caught only if a later model check also escalates, so the rules file needs tuning against the weeks 1-2 tickets.
- Rule ids appear in escalation reasons, traces and, later, evaluation results. Renaming one breaks comparisons across runs.
- Rules are checked in file order and the first match is the headline reason, so order in the file is meaningful.
- Every escalation costs two chat calls, intent and the suggested draft (from issue 03). With the call cache this is paid once per ticket.
- From issue 03 the graph enforces this structurally: the escalation in the graph state keeps its first value, so no later node can clear it (ADR 4).
- The rule about clinicians uses `requester_role`, so a ticket with no role cannot trigger it. Ticket metadata quality matters for safety.
