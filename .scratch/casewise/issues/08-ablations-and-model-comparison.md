# 08: Ablations + model comparison

**What to build:** Two tables showing that each design choice earns its place. An ablation table re-runs the evaluation with the safety rules, grounding check or retrieval threshold turned off in turn. A model comparison table runs triage on Groq Llama vs Gemini and reports accuracy, cost per ticket and latency.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] The evaluation accepts switches to turn off the safety rules, grounding check or retrieval threshold
- [ ] The ablation table reports the headline numbers for the full system and for each component turned off
- [ ] The model comparison reports accuracy, deflection, unsafe auto-replies, cost per ticket and latency for each provider
- [ ] Both tables are committed as results, and their caches are committed
- [ ] Tests: turning off a component changes the results on a fixture built to show its effect
- [ ] ADR written for what the ablations showed (or didn't)
