# 04: First evaluation run

**What to build:** `casewise eval` runs triage over a small, hand-labeled fixture set and reports the three headline numbers along with the core ML metrics. An LLM judge compares each auto-reply to its source article.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A labeled ticket format: intent, answering article (or none), must-escalate, escalation reason, metadata
- [ ] Deflection rate = correct auto-replies ÷ all tickets; a wrong auto-reply is not counted as a deflection
- [ ] Answer accuracy = correct auto-replies ÷ all auto-replies
- [ ] Unsafe auto-replies = auto-replies on must-escalate tickets
- [ ] Confusion matrix (auto-reply vs escalate) with precision and recall for each, plus escalation recall
- [ ] Intent macro-F1
- [ ] The LLM judge returns a structured correct or incorrect verdict with a reason, comparing the reply to its source article
- [ ] Output is a machine-readable results file plus a readable summary
- [ ] Tests: hand-built fixtures with known correct values for every metric, including a wrong auto-reply that must not count as deflection
- [ ] ADR written for the metric definitions and why deflection counts only correct auto-replies
