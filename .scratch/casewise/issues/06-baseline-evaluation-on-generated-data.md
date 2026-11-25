# 06: Baseline evaluation on generated data

**What to build:** The full pipeline runs over the generated dataset. Thresholds are tuned on weeks 1–2 only, and the baseline headline numbers are reported on held-out weeks 3–4. Every run is recorded in a results history so changes can be tracked.

**Blocked by:** 02, 03, 04, 05

**Status:** done

- [x] Tuning the retrieval threshold (and any grounding settings) uses only weeks 1–2
- [x] Baseline evaluation runs on weeks 3–4 with the tuned settings
- [x] Each run records the git commit, prompt version, model and all metrics in a results history
- [x] The cache for the baseline run is committed, so it reproduces with no API key
- [x] Unsafe auto-replies are 0; any that aren't are investigated and fixed through rules or checks, not by editing labels
- [x] Tests: tuning code can't read weeks 3–4
- [x] ADR written for the time-based split and the tuning protocol

## Comments

**2026-11-19 (agent):** These choices were settled with the author before the live run. ADR 7 records them.

- **Tuning:** one weeks 1–2 run with no distance cut-off, then every threshold from 0.00 to 1.00 is scored from that run. The objective is the highest deflection with 0 unsafe, and ties go to the smaller threshold.
- **Unsafe on weeks 3–4:** fix through rules or checks, and disclose that the fix was informed by held-out tickets.
- **Recording:** live, resumed from the cache once a day on Groq's free tier (200K tokens a day).

**2026-11-23 (agent):** Implemented test-first on branch `06-baseline-evaluation-on-generated-data`.

- **Interface:**
  - `casewise tune [--tickets data/tickets/weeks-1-2.jsonl] [--out eval/tuning]`, backed by `tune()`, `choose_threshold()` and `at_threshold()` in `tune.py`.
  - `casewise eval` now defaults to `data/tickets/weeks-3-4.jsonl` (`--tickets`; `--fixtures` still works). Each run appends a `RunRecord` to `eval/results/history.jsonl`.
- **Knowledge base:** triage now uses `data/kb` (25 articles). The three hand-written articles moved to `eval/fixtures-kb/`, and the issue 04 fixtures still replay with identical numbers.
- **Held-out guard:** `tune()` refuses undated tickets and anything on or after 2026-10-19, before any model call.
- **History record:** the git commit and whether the tree was dirty, the prompt version (a 12-character hash of the four triage prompts and the judge prompt), every setting, the ticket file and all metrics.
- **Tests:** 12 new tests, for 97 in all.
  - The guard, in the library and the CLI.
  - The held-out start matches the generated split.
  - Rescoring a threshold leaves rule and invalid-intent escalations alone.
  - The choice is the highest deflection with 0 unsafe, and ties go to the smaller threshold.
  - An end-to-end tuning run.
  - The default threshold equals the committed tuning result.
  - The history appends one record per run.
  - The prompt version changes with any prompt.
  - Three deliberate breaks (no guard, the sweep using the configured threshold, the threshold overriding rule escalations) each failed a test.
- **Results:**
  - **Threshold:** 0.30 (weeks 1–2: 22.0% deflection, 93.6% accuracy).
  - **First baseline:** 1 unsafe auto-reply. `gen-243` asked two things and the article answered one.
  - **Fix:** the grounding prompt now requires every part to be answered. Weeks 1–2 were re-tuned and the threshold stayed at 0.30.
  - **Final baseline (weeks 3–4):** 21.0% deflection, 97.7% answer accuracy, 0 unsafe, 100% escalation recall, intent macro-F1 0.851.
  - **Replay:** with no keys, replay reproduces `eval/tuning/` and `eval/results/latest.*` byte for byte.
- **Found along the way:**
  - The free-tier daily cap. Groq now retries 429s.
  - A Gemini call that hung for a day. It now times out after 2 minutes and retries dropped connections.
  - A test leak: with the held-out guard deliberately removed, one test ran the CLI in record mode with the real `.env` keys. Tests now blank both API keys. The stray cache entries were deleted unread.
- **For the author:** `gen-110` (an outage that no rule catches and grounding passes) is what holds the threshold at 0.30. A rule that caught it would allow 0.39, for 32.0% deflection on weeks 1–2. That is a rule change with its own baseline.
- **Caveats:**
  - Both history lines record `git_dirty: true` on `3cd3c54`, because the runs came before this branch's commit.
  - The cache grew by 1,277 chat and 425 embedding entries (11 MB in all).

**2026-11-24 (agent):** Wrap-up decisions, settled with the author before merging.

- **Clean history record:** after committing, one keyless `CASEWISE_GATEWAY_MODE=replay casewise eval` appends a third history line on the real commit. The two `git_dirty` lines stay as the record of how the baseline was reached. Issue 09 should anchor on the clean line.
- **Disclosure:** the README now says, next to the baseline, that the 0 unsafe came after a fix informed by `gen-243`. ADR 7 already said so.
- **`gen-110` rule:** left out of this branch so the baseline stays as recorded. Filed as issue 16 (`needs-triage`), not folded into 11, because 11 holds thresholds unchanged.
- **Cache:** committed in plain git, not pruned (pruning would break replay of `before-grounding-fix/`), in a commit of its own.
