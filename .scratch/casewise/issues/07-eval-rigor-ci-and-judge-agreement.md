# 07: Evaluation rigor: confidence intervals + judge agreement

**What to build:** The evaluation report shows how far each headline number could move, and checks that the judge can be trusted. Bootstrap confidence intervals go on the three headline numbers, and a second model family re-judges a sample, with Cohen's kappa reported.

**Blocked by:** 04, 05

**Status:** ready-for-agent

- [ ] Bootstrap confidence intervals on deflection rate, answer accuracy and unsafe auto-replies, with a fixed seed
- [ ] A second-family judge (Gemini) re-judges a configurable sample of auto-replies
- [ ] Cohen's kappa between the two judges is reported, with the disagreements listed
- [ ] Tests: on a known case, the interval contains the point estimate and the same seed gives the same interval
- [ ] Tests: Cohen's kappa matches a hand-computed example
- [ ] ADR written for how judge reliability is measured
