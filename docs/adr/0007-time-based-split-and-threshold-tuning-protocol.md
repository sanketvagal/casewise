# 7. A time-based split, and tuning the threshold on weeks 1–2 only

Date: 2026-11-19

Status: Accepted

## Context

Issue 06 produces the first numbers worth quoting: triage on the 400 generated tickets (ADR 6). Numbers like these get inflated when the settings are chosen on the same tickets they are reported on. The retrieval distance threshold (ADR 4) is the one setting that needs choosing. It was 0.5, a placeholder picked on three hand-written articles. The grounding check has no tunable settings: its only knob would be the prompt, and prompt changes are versioned instead (see below).

## Decision

**Split by time, not at random.** Weeks 1–2 (2026-10-05 to 2026-10-18) are the tuning split. Weeks 3–4 (from 2026-10-19) are held out. A support team tunes on the tickets it already has and lives with the results on the ones that arrive next. A random split would put the same week's phrasing in both halves and flatter the result. Topic volume is the same in both splits (ADR 6), so the split tests generalization to new tickets, not to a new topic mix.

**Tuning code cannot see weeks 3–4.** `tune()` refuses any undated ticket, and any ticket at or after `HELD_OUT_START`, before it makes a model call. `casewise tune` reads `data/tickets/weeks-1-2.jsonl` by default. Pointing it at weeks 3–4 exits with an error and writes nothing. Tests cover both.

**One sweep run, every threshold scored from it.** `tune()` triages every weeks 1–2 ticket once with no cut-off (threshold 2.0, the largest cosine distance), so each ticket's grounding verdict, draft and judge verdict are recorded. A threshold only decides whether a ticket reaches the grounding check, and nothing before that step depends on it. So the results at threshold *t* follow exactly from the sweep run:

- A ticket whose best match is beyond *t* escalates at the threshold check, unless a safety rule or invalid intent output escalated it first.
- Every other outcome is unchanged.

Thresholds from 0.00 to 1.00 in steps of 0.01 are scored this way, at no further model cost.

**The objective.** Pick the highest deflection rate among the thresholds with 0 unsafe auto-replies on weeks 1–2. Ties go to the smaller threshold. Deflection already counts only correct auto-replies (ADR 5), so a looser threshold earns nothing for wrong answers, and the tie rule refuses to loosen the threshold for nothing. The chosen value becomes the default `distance_threshold`. A test fails if the default and `eval/tuning/weeks-1-2.json` disagree.

**The baseline** is `casewise eval` on weeks 3–4 with the tuned settings and the 25-article generated knowledge base (`data/kb`). The three hand-written articles behind the issue 04 fixtures moved to `eval/fixtures-kb/`.

**Every run is on record.** Each `casewise eval` appends one line to `eval/results/history.jsonl`. The line holds the time, the git commit and whether tracked files were dirty, the prompt version, every setting, the ticket file, and all metrics. The prompt version is a 12-character hash of the four triage prompts and the judge prompt, so rewording any of them shows in the history without anyone remembering to bump a number.

**Unsafe auto-replies on weeks 3–4 are fixed and disclosed.** If the baseline has any, they are fixed through the rules or the checks, never by editing labels. The history keeps both the first baseline and the post-fix one, and this ADR says that the fix was informed by held-out tickets.

## Results

Recorded live from 2026-11-19 to 2026-11-23. Triage ran on `openai/gpt-oss-120b`, the judge on `gemini-3.5-flash-lite`. Groq's free tier allows 200K tokens a day, so the recording took four daily runs.

**Tuning (weeks 1–2, `eval/tuning/weeks-1-2.md`).** The threshold is 0.30: 22.0% deflection, 93.6% answer accuracy, 0 unsafe. One ticket pins it. `gen-110` is an outage ticket ("payment gateway failing for all credit card transactions") that no keyword rule catches and the grounding check passes. It sits at 0.309, so every threshold above 0.30 lets an unsafe reply through. Without it, 0.39 would give 32.0% deflection. Catching it with a rule is a rule change with its own baseline (ADR 6), so it was left for the author to decide.

**First baseline (weeks 3–4, history line 1, prompt version `685c9f8e0cbe`).** 21.5% deflection, 95.6% answer accuracy, **1 unsafe auto-reply**. `gen-243` asks how to create staff accounts (a simulated gap) and how to assign their permissions. The grounding check passed `configure-roles-and-permissions` because it answered the second half. The reply never covered creating the accounts.

**The fix, informed by weeks 3–4.** The grounding prompt now says: if the ticket asks for more than one thing, the article must answer all of them. No label was changed. Because the prompt changed, the threshold was re-tuned on weeks 1–2. It stayed at 0.30, with one fewer correct reply (22.5% to 22.0%). The pre-fix tuning and baseline are kept in `eval/tuning/before-grounding-fix/` and `eval/results/before-grounding-fix/`.

**Baseline (weeks 3–4, history line 2, prompt version `d5aa44631354`).**

| Metric | Value |
| --- | --- |
| Deflection rate | 21.0% (42 correct / 200) |
| Answer accuracy | 97.7% (42 / 43 auto-replies) |
| Unsafe auto-replies | 0 |
| Escalation recall | 100% (103 / 103) |
| Intent macro-F1 | 0.851 |

The one incorrect reply (`gen-358`) cited the right article and added a step the article doesn't contain. Deflection is held down by the keyword rules escalating routine tickets (ADR 6: 99 of 320 routine tickets match a rule) and by the tight threshold. 54 of the 97 tickets that weren't must-escalate were escalated.

Because the fix was informed by weeks 3–4, those 200 tickets are no longer fully untouched. The 0 unsafe was reached on the same tickets that prompted the fix, so it is optimistic by up to that one ticket. The first baseline, with its 1 unsafe reply, is the cleaner held-out number, and both stay in the history.

## Considered options

- **A random split.** Rejected: see above.
- **Re-running triage at each candidate threshold.** Rejected: it gives the same answer as the sweep for about 100 times the calls, which the free tiers can't pay for.
- **An accuracy floor (for example 90%) as well as 0 unsafe.** Not chosen: deflection already ignores wrong replies, and the tie rule stops pointless loosening. Revisit if answer accuracy at the chosen threshold looks poor.
- **Tuning on cross-validation folds over all 400 tickets.** Rejected: it lets the held-out fortnight shape the setting.

## Consequences

- Weeks 1–2 have now been looked at closely. Anything learned from them (rule changes, prompt changes) is fair game. Anything learned from weeks 3–4 has to be disclosed as above.
- A prompt, rule or knowledge-base change can move the best threshold. Re-run `casewise tune` after one. It reuses the cache for everything that didn't change.
- The sweep relies on nothing before the threshold check depending on the threshold. If a future step before it reads the threshold, the sweep stops being exact and this ADR must be revisited.
- Issue 09's regression gate reads its baseline from the results history.
