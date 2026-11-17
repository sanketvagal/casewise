# 03: Intent classification, grounding check, structured outputs

**What to build:** The triage graph gains an intent classification step and an LLM grounding check ("does this article actually answer this ticket?"). Every LLM step returns validated structured output and retries on malformed output. Grounding failures and repeated validation failures escalate. No LLM step can move a ticket away from escalation.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Triage runs as a LangGraph state graph: safety rules (or a placeholder for them) → intent → retrieval → threshold → grounding → draft or escalate
- [ ] Every LLM step returns a validated Pydantic model (intent with confidence, grounding verdict with reason, draft with cited article)
- [ ] Validation failures retry a set number of times, then escalate, never auto-reply
- [ ] A grounding "no" escalates, with the reason recorded
- [ ] Each trace record includes the intent and the grounding verdict
- [ ] Tests: a close embedding match on the wrong question (placing vs cancelling a lab order) escalates when the grounding check says no
- [ ] Tests: malformed output followed by valid output succeeds, and malformed output that keeps failing escalates
- [ ] Tests: none of the LLM steps can turn an escalation into an auto-reply
- [ ] ADR written for the two-check confidence design (retrieval threshold plus grounding)
