# 09: CI regression gate

**What to build:** The evaluation runs like a test suite. On every push, CI re-runs the evaluation from the committed cache with no API keys. It fails if any unsafe auto-reply appears, if deflection drops more than a set tolerance below the recorded baseline, or if the cache can't reproduce the recorded numbers.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] The CI evaluation job runs with no provider keys present
- [ ] It fails when unsafe auto-replies are above 0
- [ ] It fails when deflection drops more than the configured tolerance below the baseline in the results history
- [ ] It fails when a cache miss would require a live call
- [ ] Tests: the gate logic fails and passes on synthetic results histories
- [ ] ADR written for treating evaluations as tests and for the tolerance chosen
