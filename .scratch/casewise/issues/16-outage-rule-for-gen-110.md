# 16: An outage rule for gen-110, and the baseline it moves

**What to build:** A safety rule (or check) that escalates outage tickets like `gen-110` ("payment gateway failing for all credit card transactions"), which today no keyword rule catches and the grounding check passes. Then re-tune the threshold on weeks 1–2 and record a new baseline on weeks 3–4.

**Blocked by:** 06

**Status:** needs-triage

## Context

- `gen-110` is in weeks 1–2, so learning from it is allowed and needs no disclosure (ADR 7).
- Its best match sits at cosine distance 0.309. Every threshold above 0.30 lets it through as an unsafe auto-reply, so it alone holds the tuned threshold at 0.30.
- With it caught, the tuning sweep would choose 0.39, for 32.0% deflection on weeks 1–2 (against 22.0% today).
- This is a rule change, so it gets its own baseline entry in `eval/results/history.jsonl` (ADR 6). It was kept out of issue 06 so the 06 baseline stays as recorded.
- It doesn't belong in issue 11, which holds thresholds unchanged so its before and after compare only new articles.

## Acceptance

- [ ] The rule catches `gen-110` without being written as a match on that one ticket's wording
- [ ] Re-run `casewise tune` on weeks 1–2, and the default threshold follows the new result
- [ ] Re-run `casewise eval` on weeks 3–4, appending a new history line; report the change in deflection, accuracy, unsafe and escalation recall against the issue 06 baseline
- [ ] Check how many weeks 1–2 routine tickets the new rule escalates (ADR 6: rules already escalate 99 of 320 routine tickets)
- [ ] Cache committed, so the new numbers replay with no API key
