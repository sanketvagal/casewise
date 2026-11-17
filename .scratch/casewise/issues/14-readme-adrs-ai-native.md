# 14: README, ADR index, AI-native section

**What to build:** A README that gets the project across in ten seconds. It opens with the one-liner and the three headline numbers with confidence intervals, followed by the ML, ablation, model-comparison and before-and-after tables, a triage-graph diagram, a plain statement of how data and gaps were simulated, a "Built AI-native" section, the demo link and an index of the ADRs. CI checks that the README numbers match the latest results.

**Blocked by:** 08, 09, 11, 13

**Status:** ready-for-agent

- [ ] The README opens with "casewise: safety-first LLM triage for clinical SaaS support, with evals that prove it." and the three headline numbers with confidence intervals
- [ ] Includes the ML, ablation, model-comparison and before-and-after tables
- [ ] Includes a triage-graph diagram
- [ ] Includes an honest description of the synthetic data, labels-first generation and simulated gaps
- [ ] "Built AI-native" section: what AI tools did, what the author decided, and where the author overruled the AI
- [ ] Includes the demo link and an index linking every ADR
- [ ] A CI check fails when the README numbers don't match the latest results history
- [ ] CLAUDE.md is committed
- [ ] Doesn't name or frame the project around any single company
