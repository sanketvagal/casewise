# 13: Live triage box + deploy

**What to build:** A "try your own ticket" box in the demo that triages a reviewer's own ticket live and shows its trace. Usage is rate-limited and capped per day so a public link can't run up costs. The demo is deployed to a public URL.

**Blocked by:** 12

**Status:** ready-for-agent

- [ ] The live box runs the real pipeline and shows the decision, handoff packet (if escalated) and trace
- [ ] Per-session rate limit and a global daily cap; once the cap is reached, the box explains that and the precomputed views keep working
- [ ] The API key is read from deployment secrets and never committed
- [ ] Deployed to a free public host, with the URL recorded for the README
- [ ] ADR written for the cost-protection design
