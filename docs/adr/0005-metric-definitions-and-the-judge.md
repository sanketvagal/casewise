# 5. Metric definitions: deflection counts only correct auto-replies; judge is a different family

Date: 2026-11-17

Status: Accepted

## Context

The headline numbers (deflection rate, answer accuracy, unsafe auto-replies) are what the project is judged on, so each one has to survive a skeptical reader. The obvious definition of deflection, "tickets not escalated", rewards a system that auto-replies to everything, including wrongly. Correctness needs a judge, and a judge that shares a family with the triage model, or is shown the article the system itself picked, can approve the system's own mistakes.

## Decision

**Correct auto-reply.** An auto-reply is correct only if all three hold:

1. the ticket is not must-escalate
2. the cited article equals the labeled answering article
3. the judge marks the reply correct

If (1) or (2) fails, the reply is incorrect and the judge is not called. If the judge's output stays invalid after the usual retries (ADR 4), the reply is recorded as `unjudged` and counted as incorrect.

**Headline metrics.**

- Deflection rate = correct auto-replies ÷ all tickets. A wrong auto-reply counts as a failure, not a deflection.
- Answer accuracy = correct auto-replies ÷ all auto-replies.
- Unsafe auto-replies = the count of auto-replies on must-escalate tickets. The target is 0.

**Routing metrics score the decision only.** The ground truth for "escalate" is `must_escalate`, which is true when a safety rule applies or no article answers the ticket. The confusion matrix (auto-reply vs escalate), per-class precision and recall, and escalation recall compare the predicted decision with that label. Any escalation path counts toward recall: a ticket labeled with a rule that escalates on the retrieval threshold is still a correct escalation. Agreement between the actual and the expected escalation reason (rule ids plus `no_answer`) is reported for information but scores nothing.

**Intent macro-F1** runs over every ticket, rule-escalated ones included, and averages over the classes present in the gold labels. Invalid intent output counts as a wrong prediction.

**The judge** sees the ticket, the reply and the **labeled** answering article, never the article retrieval picked. It returns a structured `correct`/`incorrect` verdict with a reason. It marks a reply correct only if the reply answers the ticket's question, agrees with the article and adds no claims the article doesn't support. It runs on a different model family from triage: Gemini Flash-Lite through its own `judge_provider` and `judge_model` settings, behind the same gateway seam (ADRs 1 and 2).

## Considered options

- **Deflection = non-escalated ÷ all.** Rejected: it counts wrong answers as wins.
- **Judge only, without checking the citation.** Rejected: a fluent reply built on the wrong article could pass.
- **Judge with gpt-oss-120b (the triage model).** Rejected: a model judging its own family is the first thing a reviewer questions.
- **Gemini Flash rather than Flash-Lite.** Deferred: in October 2026 the free tier allowed about 20 Flash requests a day against about 500 for Flash-Lite, which rules Flash out for judging 400 tickets. Issue 07 measures judge agreement. If Flash-Lite proves too weak there, moving to paid Flash is a config change.

## Consequences

- Deflection is never higher than the share of tickets that are not must-escalate, so it can't be gamed by auto-replying more.
- Two gateways are needed during evaluation (triage and judge), and both are cached. Judge entries are keyed by their own model, so they never collide with triage entries.
- Judge strictness becomes a lever on the headline numbers. The rubric is fixed here and changing it starts a new baseline.
