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

## Comments

**2026-11-17 (agent):** Design settled in a grilling session before coding. Definitions are in `GLOSSARY.md` and ADR 5.

- **Correct auto-reply:** the ticket is not must-escalate, the cited article equals the labeled answering article, and the judge says correct. If either of the first two fails, the reply is incorrect and the judge isn't called. Judge output that stays invalid → `unjudged`, counted as incorrect.
- **Judge:** sees the ticket, the reply and the **labeled** article. Rubric: answers the question, agrees with the article, adds no unsupported claims. Output is `JudgeVerdict{verdict, reason}` through `structured.py`. It runs on Gemini Flash-Lite (free tier about 500 requests a day; Flash is about 20), set by separate `judge_provider` and `judge_model` settings. The Gemini chat provider is built in this issue.
- **Routing:** `must_escalate` (a rule applies, or no answering article) is the ground truth for the confusion matrix and escalation recall. Any escalation path counts. Reason agreement (rule ids plus `no_answer`) is reported for information only.
- **Intent macro-F1:** over all tickets, using the current `intent_labels()` (article ids plus `other`), averaged over the gold classes. Invalid output counts as wrong.
- **Interface:** `evaluate(labeled_tickets, gateway, judge_gateway, settings) -> EvalResults`. Tests script each gateway separately.
- **Fixtures:** about 12 hand-labeled tickets in `eval/fixtures.jsonl`, covering each article, each rule category, a threshold miss and the cancel-vs-reschedule near-miss. Metric tests build their own tiny fixtures.
- **Output:** `eval/results/latest.json` (metrics plus per-ticket rows) and `eval/results/latest.md` (also printed). One live recording goes into the committed `cache/`, and replay with no keys must reproduce it.
- **Out of scope:** bootstrap CIs and kappa (07), ablations and the model comparison (08), run history and the CI gate (09).
