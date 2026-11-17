# 02: Safety rules + handoff packet

**What to build:** Deterministic safety rules, kept in a readable config file, escalate a ticket before any LLM decision is made. The escalation names the rule that fired. Every escalation, whatever triggered it, comes with a handoff packet that makes the human agent faster.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Rules live in a human-readable config file, and each rule has a stable identifier
- [x] Rules cover patient-data access or exposure, prescriptions and e-prescribing errors, billing disputes, suspected outages, and upset or urgent clinicians (requester role is an input)
- [x] A rule match goes straight to escalation, and no later step can turn it into an auto-reply
- [x] The escalation reason names the exact rule identifier or check that failed
- [x] The handoff packet contains the escalation reason, detected intent (when available), top retrieved articles, a suggested draft marked "for human review", and a suggested next step
- [x] Tests: a prescription-error ticket from a physician escalates even when the fake gateway would auto-reply
- [x] Tests: each rule category fires on a representative ticket and stays silent on a near-miss
- [x] Tests: every escalation includes a complete handoff packet
- [x] ADR written for "rules first; the LLM can only add escalations, never remove them"

## Comments

**2026-11-17 (agent):** Implemented test-first. Notes for later tickets:

- Rules live in `safety_rules.yaml` at the repo root (`CASEWISE_RULES_PATH` overrides). Phrase lists are a first pass written by hand, not yet tuned against generated tickets.
- Every escalation makes one chat call for the suggested draft, including weak-match escalations that made none before. The trace step is `draft_for_review`.
- After a rule match the `threshold_check` step is skipped, so its trace record is absent for those runs.
- `handoff.detected_intent` is always `None` until issue 03 adds the intent step.
- Checked live on `openai/gpt-oss-120b`: a physician's wrong-pharmacy ticket escalated on `prescription_error` (also matching `urgent_clinician`), and a fax ticket escalated on `retrieval_threshold`. Both recorded runs are in `cache/`.
