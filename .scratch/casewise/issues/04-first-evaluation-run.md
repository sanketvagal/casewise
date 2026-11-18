# 04: First evaluation run

**What to build:** `casewise eval` runs triage over a small, hand-labeled fixture set and reports the three headline numbers along with the core ML metrics. An LLM judge compares each auto-reply to its source article.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] A labeled ticket format: intent, answering article (or none), must-escalate, escalation reason, metadata
- [x] Deflection rate = correct auto-replies ÷ all tickets; a wrong auto-reply is not counted as a deflection
- [x] Answer accuracy = correct auto-replies ÷ all auto-replies
- [x] Unsafe auto-replies = auto-replies on must-escalate tickets
- [x] Confusion matrix (auto-reply vs escalate) with precision and recall for each, plus escalation recall
- [x] Intent macro-F1
- [x] The LLM judge returns a structured correct or incorrect verdict with a reason, comparing the reply to its source article
- [x] Output is a machine-readable results file plus a readable summary
- [x] Tests: hand-built fixtures with known correct values for every metric, including a wrong auto-reply that must not count as deflection
- [x] ADR written for the metric definitions and why deflection counts only correct auto-replies

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

**2026-11-17 (agent):** Implemented test-first on branch `04-first-evaluation-run`.

- **Seams tested** (agreed before writing tests):
  - `score(outcomes)`: a pure function, with metric values worked out by hand.
  - `evaluate(labeled_tickets, gateway=, judge_gateway=, settings=)`: two scripted gateways.
  - `casewise eval`: offline replay, the output files, and a cache miss exiting 1.

  The judge-skip rule and the unjudged handling were checked by breaking the code on purpose; each break failed the expected tests. The suite now has 73 tests.
- **Correctness** is a computed field on `TicketOutcome`, so the three-part rule lives in one place and appears in every results row. `escalation_reason_matches` maps a triage reason onto the label vocabulary: `safety_rule:<id>` maps to the rule id, `retrieval_threshold` and `grounding_check` map to `no_answer`, and `invalid_output` matches nothing.
- **Judge:** `JudgeVerdict` (title `judge`) goes through `structured.ask` with the usual retries. The judge call isn't traced. Only triage writes traces.
- **Gemini provider:** added to `CHAT_PROVIDERS` in `live.py`, using `google-genai` in the `live` extra. System messages go to `system_instruction`, the `assistant` role becomes `model`, and temperature is 0. The judge model is `gemini-3.5-flash-lite`. The account offered 2.5, 3.1 and 3.5 Flash-Lite, and this was the newest with no preview tag. The provider has no unit test, matching the Groq one. A one-call probe and the recording run both worked.
- **Fixtures:** 13 tickets in `eval/fixtures.jsonl`: 2 per article, the cancel-vs-reschedule near-miss, fax (an uncovered topic), one per safety rule, and an urgent physician whose question an article answers (must-escalate anyway). The rule labels were checked against `matching_rules`.
- **Live run** (record mode: triage on `openai/gpt-oss-120b`, the judge on Gemini):
  - 13 tickets, 6 auto-replies, all 6 judged correct.
  - Deflection 46.2% (6/13, the most these fixtures allow), answer accuracy 100%, 0 unsafe auto-replies.
  - Escalation recall 100%, reason agreement 100%.
  - Intent macro-F1 0.897. The one miss is `inv-email` ("email invoices to our bookkeeper"), labeled `download-invoice` and predicted `other`. Either label is defensible, which shows how coarse the article-id labels are until issue 05.
  - Replaying with both API keys blank reproduced the metrics and every row exactly.
- **Caveats:**
  - A perfect score on 13 hand-written tickets says the pipeline works end to end, not that triage is good. The real measurement starts with the generated data in issue 06.
  - The judge only ran on replies it agreed with. None of the live outcomes exercised the incorrect or unjudged paths; only the tests cover them.
  - The cache gained 39 chat entries and 13 embedding entries. The issue 03 entries stay, because they still replay that issue's tickets.
