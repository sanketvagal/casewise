# 06: Baseline evaluation on generated data

**What to build:** The full pipeline runs over the generated dataset. Thresholds are tuned on weeks 1–2 only, and the baseline headline numbers are reported on held-out weeks 3–4. Every run is recorded in a results history so changes can be tracked.

**Blocked by:** 02, 03, 04, 05

**Status:** ready-for-agent

- [ ] Tuning the retrieval threshold (and any grounding settings) uses only weeks 1–2
- [ ] Baseline evaluation runs on weeks 3–4 with the tuned settings
- [ ] Each run records the git commit, prompt version, model and all metrics in a results history
- [ ] The cache for the baseline run is committed, so it reproduces with no API key
- [ ] Unsafe auto-replies are 0; any that aren't are investigated and fixed through rules or checks, not by editing labels
- [ ] Tests: tuning code can't read weeks 3–4
- [ ] ADR written for the time-based split and the tuning protocol
