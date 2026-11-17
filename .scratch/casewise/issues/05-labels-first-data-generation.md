# 05: Labels-first data generation

**What to build:** One command generates the fictional clinical SaaS world. It produces a product spec of about 40 support topics, then per-ticket labels, then ticket text written *from* those labels (about 400 tickets across weeks 1–2 and 3–4), and an initial knowledge base covering only about 25 of the topics. Generation uses a different model family (Gemini) from triage.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Gemini implementation added to the model gateway
- [ ] The product spec covers scheduling, e-prescribing, lab orders and results, billing, and the patient portal for a fictional, unbranded product
- [ ] Labels are generated before ticket text, and ticket text is generated from them
- [ ] Each ticket has a subject, body, requester role (physician, front desk, biller, practice admin), practice size, plan tier and timestamp
- [ ] Tickets vary in tone and level of detail
- [ ] About 200 tickets in weeks 1–2 and about 200 in weeks 3–4, split by timestamp
- [ ] The initial knowledge base covers about 25 of the 40 topics, and the uncovered topics are recorded for later scoring only, never shown to triage or insights
- [ ] A share of tickets is must-escalate, matching the safety-rule categories
- [ ] Generated data is committed, along with the cache that produced it
- [ ] Tests (light): labels exist before text, knowledge-base coverage matches the intended topics, the week split holds, metadata is complete
- [ ] ADR written for labels-first generation, the cross-family generator, and simulated gaps
