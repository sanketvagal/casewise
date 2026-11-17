# 02: Safety rules + handoff packet

**What to build:** Deterministic safety rules, kept in a readable config file, escalate a ticket before any LLM decision is made. The escalation names the rule that fired. Every escalation, whatever triggered it, comes with a handoff packet that makes the human agent faster.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Rules live in a human-readable config file, and each rule has a stable identifier
- [ ] Rules cover patient-data access or exposure, prescriptions and e-prescribing errors, billing disputes, suspected outages, and upset or urgent clinicians (requester role is an input)
- [ ] A rule match goes straight to escalation, and no later step can turn it into an auto-reply
- [ ] The escalation reason names the exact rule identifier or check that failed
- [ ] The handoff packet contains the escalation reason, detected intent (when available), top retrieved articles, a suggested draft marked "for human review", and a suggested next step
- [ ] Tests: a prescription-error ticket from a physician escalates even when the fake gateway would auto-reply
- [ ] Tests: each rule category fires on a representative ticket and stays silent on a near-miss
- [ ] Tests: every escalation includes a complete handoff packet
- [ ] ADR written for "rules first; the LLM can only add escalations, never remove them"
