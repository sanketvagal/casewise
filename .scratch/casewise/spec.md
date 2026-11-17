# Spec: casewise

Status: ready-for-agent

> casewise: safety-first LLM triage for clinical SaaS support, with evals that prove it.

## Problem Statement

I'm a technical support professional with a Master's in Applied Computer Science, moving into AI/LLM application engineering. Bridge roles (support engineer, solutions engineer, AI-ops support roles) are my fallback. My resume shows strong support experience (escalations, root-cause analysis, 50+ knowledge-base articles, SQL dashboards) and several small AI projects (RAG over notes, a LangGraph research agent, a Gemini function-calling agent). None of those projects shows production-grade AI engineering. None measures whether the system works, guards against unsafe behavior, or changes a business metric.

Hiring managers for AI engineering and AI-ops roles want evidence that I can configure and supervise AI systems, evaluate them rigorously, and turn patterns in the data into decisions. Bridge roles such as AI-first support teams also ask for "2–3 things built or shipped that changed a metric" and "an insight that changed someone else's decision". I have no single project that answers both questions credibly.

## Solution

casewise is an AI triage copilot for the support team of a fictional clinical SaaS product: practice-management software covering scheduling, e-prescribing, lab orders and results, billing and the patient portal. All data is synthetic, and the project does not use any real company's name or branding.

For each incoming support ticket, casewise either:

- **auto-replies** with an answer grounded in the knowledge base, but only when deterministic safety rules allow it and two independent confidence checks pass, or
- **escalates** to a human with a handoff packet: why it escalated, the detected intent, the top articles found, a suggested draft for review, and a suggested next step.

casewise also produces a **weekly insights report**. It clusters escalated tickets into recurring problems and names the likely knowledge-base gap or product defect behind each one. This drives the project's headline story: the report finds gaps in weeks 1–2, the missing articles get written, and deflection measurably rises on unseen weeks 3–4 tickets.

Everything is measured. There are three headline numbers (deflection rate, answer accuracy, unsafe auto-replies), backed by a full ML metrics table, bootstrap confidence intervals, judge-agreement statistics, a model comparison and an ablation study. The evaluation runs like a test suite in CI. A reviewer can clone the repo and reproduce every number without an API key, because every model call is cached.

The project is explicitly built AI-native. The README documents what AI tools did, what the author decided, and where the author overruled the AI.

## User Stories

### Author (the developer building and presenting the project)

1. As the author, I want a single README line with three headline numbers, so that I can paste a credible, metric-backed claim into a cover letter or resume.
2. As the author, I want a before-and-after deflection result caused by an insight, so that I have a true story about an insight that changed a decision.
3. As the author, I want every design decision recorded as a short ADR, so that I can explain and defend the design in interviews without notes or AI tools.
4. As the author, I want a "Built AI-native" README section, so that reviewers can see I configure and supervise AI tools rather than just use them.
5. As the author, I want the repo's agent configuration (CLAUDE.md, ADRs) committed, so that my AI-assisted workflow is visible and reproducible.
6. As the author, I want to switch the default model provider with one configuration setting, so that I can compare models and avoid lock-in.
7. As the author, I want every model call cached on disk, keyed by model and prompt, so that re-running the evaluation costs nothing and returns identical numbers.
8. As the author, I want a CLI with `triage`, `eval` and `insights` commands, so that I can run the whole system from a terminal and script it in CI.
9. As the author, I want CI to fail if unsafe auto-replies go above zero or deflection drops by more than a set amount, so that a prompt change can't silently make things worse.
10. As the author, I want each evaluation run recorded with its git commit and prompt version, so that I can see how results changed over time.
11. As the author, I want a 2-minute video walkthrough linked from the README, so that busy reviewers can understand the project without running it.
12. As the author, I want the demo's live mode rate-limited and capped per day, so that a public link can't run up costs on my API key.

### Data generation

13. As the author, I want the system to generate a product spec of about 40 support topics for the fictional clinical product, so that tickets cover realistic, varied problems.
14. As the author, I want each ticket's labels (intent, answering article, must-escalate yes or no, escalation reason) generated before the ticket text, so that the correct answer is known by construction rather than inferred afterward.
15. As the author, I want tickets generated by a different model family from the one running triage, so that the bot isn't graded on data in its own style.
16. As the author, I want about 400 single-message tickets, each with a subject, body and metadata (requester role, practice size, plan tier, timestamp), so that the dataset is large enough for stable percentages.
17. As the author, I want tickets to vary in tone, detail and requester role (physician, front desk, biller, practice admin), so that the triage faces realistic variety.
18. As the author, I want the tickets split by timestamp into weeks 1–2 (200) and weeks 3–4 (200), so that tuning and gap-finding never touch the held-out evaluation set.
19. As the author, I want the initial knowledge base to cover only about 25 of the 40 topics, so that the gaps are simulated realistically and the insights report has something real to find.
20. As the author, I want the README to state plainly how data and gaps were simulated, so that the project is honest about being synthetic.

### Triage pipeline

21. As a clinic customer, I want simple, documented questions answered immediately and correctly, so that I don't wait on a human for routine help.
22. As a clinic customer, I want anything involving patient data, prescriptions, billing disputes or a suspected outage to reach a human, so that high-stakes problems are never handled by an unsupervised bot.
23. As a support lead, I want hard-coded safety rules evaluated before any LLM decision, so that certain ticket types always escalate regardless of model output.
24. As a support lead, I want the LLM to be able to add escalations but never remove one triggered by a rule, so that the model can't override the safety rules.
25. As a support lead, I want the safety rules in a readable configuration, so that I can audit and adjust them without reading code.
26. As a support lead, I want requester role to affect escalation (e.g. a physician reporting a prescription error), so that urgent clinical cases are prioritized.
27. As a support lead, I want auto-replies only when the best knowledge-base match passes a retrieval distance threshold, so that weak matches never produce answers.
28. As a support lead, I want an LLM grounding check confirming the article actually answers the ticket, so that tickets that look similar but ask different questions (e.g. placing vs cancelling a lab order) are caught.
29. As a support lead, I want confidence thresholds tuned only on weeks 1–2, so that the held-out results stay honest.
30. As a support agent receiving an escalation, I want a handoff packet with the reason, intent, top articles, a suggested draft for review and a next step, so that I resolve escalations faster.
31. As a support agent, I want the escalation reason to name the exact rule or check that failed, so that I trust and understand the routing.
32. As a support lead, I want every LLM node to return validated, structured output and retry when validation fails, so that malformed output never breaks the pipeline or slips through.
33. As a support lead, I want every auto-reply to cite the article it's based on, so that answers can be checked against their source.

### Tracing and observability

34. As an AI engineer reviewing the project, I want every ticket's run recorded as a trace (each node's input, output, latency, tokens and decision), so that I can see exactly why any ticket escalated or auto-replied.
35. As an AI engineer, I want traces to work with cached replay, so that inspecting a run never needs a live model.
36. As a demo viewer, I want a trace replay view, so that I can step through the graph's decisions for a real ticket.

### Evaluation

37. As a reviewer, I want the deflection rate defined as correct auto-replies ÷ all tickets, so that wrong auto-replies count as failures, not deflections.
38. As a reviewer, I want answer accuracy defined as correct auto-replies ÷ all auto-replies (precision), so that I know how far to trust an auto-reply.
39. As a reviewer, I want unsafe auto-replies counted as auto-replies on must-escalate tickets, with a target of zero, so that safety is measured, not claimed.
40. As a reviewer, I want a confusion matrix of auto-reply vs escalate with precision and recall for each, so that I can see the full trade-off.
41. As a reviewer, I want escalation recall reported (target 100%), so that I can confirm no must-escalate ticket was missed.
42. As a reviewer, I want macro-F1 for intent classification across all topics, so that I can judge the classifier separately from the routing.
43. As a reviewer, I want bootstrap confidence intervals on the headline numbers, so that I know how much they could vary at this sample size.
44. As a reviewer, I want correctness judged by an LLM against the ticket's source article, with a second model family re-judging a sample and Cohen's kappa reported, so that the judge's reliability is itself measured.
45. As a reviewer, I want a model comparison table (Groq Llama vs Gemini) covering accuracy, cost per ticket and latency, so that I can see the author thinks about production trade-offs.
46. As a reviewer, I want an ablation table showing results with the safety rules, grounding check and retrieval threshold each turned off in turn, so that I can see each component's contribution.
47. As a reviewer, I want to reproduce every reported number from a fresh clone with no API key, so that I can trust the results.
48. As a reviewer, I want a check that the README numbers match the latest cached evaluation, so that the documentation can't drift from reality.

### Insights

49. As a product manager, I want a weekly insights report of the top recurring escalation clusters by volume, so that I know where customers struggle most.
50. As a product manager, I want each cluster named, summarized, illustrated with example tickets and labeled as a likely knowledge-base gap or product defect, so that I can act on it.
51. As a product manager, I want each cluster to come with a recommended action, so that the report leads to decisions rather than just observations.
52. As the author, I want clustering that doesn't need the number of clusters chosen up front, so that the report finds whatever patterns actually exist.
53. As the author, I want the insights report run on weeks 1–2 only, so that the gaps it finds can be fixed and measured on unseen weeks 3–4.
54. As the author, I want to add new knowledge-base articles for the gaps found and re-run the evaluation on weeks 3–4, so that I get a before-and-after result.
55. As a reviewer, I want the before-and-after comparison reported with confidence intervals, so that I can tell whether the improvement is real.
56. As a reviewer, I want to see how many simulated gaps the report found without being told, so that I can judge how well the insights engine discovers gaps.

### Demo

57. As a reviewer, I want a hosted demo showing precomputed results by default, so that I can explore it instantly at no cost.
58. As a reviewer, I want an evaluation dashboard in the demo (headline numbers, ML table, ablations, model comparison, before and after), so that every result is in one place.
59. As a reviewer, I want the weekly insights report shown in the demo, so that I can read what Product and Engineering would read.
60. As a reviewer, I want to type my own ticket and watch it get triaged live, within a rate limit, so that I can test the system myself.
61. As a reviewer, I want a diagram of the triage graph in the README, so that I understand the architecture at a glance.

## Implementation Decisions

- **Domain:** a fictional clinical SaaS practice-management product. All data is synthetic, with no real patient data and no real company branding. The regulated domain is deliberate: it gives the safety rules and the unsafe-auto-reply metric real weight.
- **Language and tooling:** Python, managed with uv, tested with pytest and linted with ruff. GitHub Actions runs the tests and the cached evaluation regression check on every push. The project is a new standalone git repo named `casewise`.
- **Packaging:** an importable library with three public entry points (triage, evaluate, insights) plus data generation. A CLI wraps them: `casewise triage | eval | insights`, plus a data-generation command. The Streamlit demo is only a client of the library.
- **Model gateway (the single substitution seam):** every chat completion and every embedding goes through one gateway interface. It has three implementations: a real one (Groq Llama by default, Gemini as an alternative, Sentence Transformers for embeddings), cached replay (an on-disk cache keyed by model and prompt), and a scripted fake for tests. The default provider is chosen by configuration. Data generation and judging use a different model family from triage.
- **Structured outputs:** every LLM node returns a validated Pydantic model, e.g. intent with confidence, the grounding verdict with a reason, a draft with its cited article, a judge verdict. Validation failures are retried a set number of times and then treated as an escalation, never as an auto-reply.
- **Pipeline:** a LangGraph state graph: safety rules → intent classification → retrieval → retrieval-threshold check → grounding check → draft reply, or escalate with a handoff packet. A triggered rule short-circuits to escalation. LLM nodes can only move a ticket toward escalation, never away from it.
- **Safety rules:** deterministic, kept in a human-readable configuration file. They cover patient-data access or exposure, prescriptions and e-prescribing errors, billing disputes, suspected outages, and upset or urgent clinicians (with requester role as an input). Each rule has an identifier that appears in the escalation reason.
- **Retrieval:** knowledge-base articles are embedded and stored in a vector store (ChromaDB, following the RAG Notes prior art). The best match must fall within a cosine-distance threshold. The threshold and any grounding settings are tuned on weeks 1–2 only.
- **Handoff packet:** escalation reason (rule or check identifier), detected intent, top retrieved articles, a suggested draft clearly marked for human review, and a suggested next step.
- **Data generation, labels first:** product spec (~40 topics) → per-ticket labels (intent, answering article or none, must-escalate, escalation reason, metadata) → ticket text generated from those labels. The initial knowledge base covers about 25 of the 40 topics. Weeks 1–2 and weeks 3–4 are split by timestamp, about 200 tickets each.
- **Ticket shape:** a single message with subject, body, requester role (physician, front desk, biller, practice admin), practice size, plan tier and timestamp. No multi-turn conversations.
- **Tracing:** every triage run writes a JSONL trace with one record per node (input, output, latency, token usage, decision). Traces are produced the same way under cached replay. A hosted tracing service (Langfuse or LangSmith) is an optional future add-on, not part of this spec.
- **Metric definitions:**
  - Deflection rate = correct auto-replies ÷ all tickets.
  - Answer accuracy = correct auto-replies ÷ all auto-replies.
  - Unsafe auto-replies = count of auto-replies on must-escalate tickets (target 0).
  - Supporting metrics: a confusion matrix (auto-reply vs escalate), precision and recall for each, escalation recall (target 100%), intent macro-F1, bootstrap confidence intervals on the headline numbers, and Cohen's kappa between the primary judge and the second-family judge on a sample.
- **Judging:** an LLM judge compares each auto-reply to the ticket's source article and returns a structured correct-or-incorrect verdict with a reason. A second model family re-judges a sample, and agreement is reported.
- **Ablations:** the evaluation can be run with any of the safety rules, grounding check or retrieval threshold turned off. Ablation results are a table in the report.
- **Model comparison:** the same evaluation is run per provider, reporting accuracy, cost per ticket and latency.
- **Evaluation history and regression gate:** each run records the git commit, prompt version, model and metrics in a results history. CI fails if unsafe auto-replies exceed 0, if deflection drops more than a set tolerance below the recorded baseline, or if the README numbers don't match the latest results.
- **Insights:** escalated tickets are embedded and clustered with HDBSCAN. An LLM names and summarizes each cluster, classifies it as a likely knowledge-base gap or product defect, and recommends an action. The output is a Markdown weekly report, ordered by cluster volume, with example tickets.
- **Before-and-after loop:** the insights report runs on weeks 1–2, the articles it calls for get written, and the evaluation is compared before and after on weeks 3–4. The report also states how many of the simulated gaps were found.
- **Demo:** Streamlit, deployed publicly. Precomputed results are shown by default: evaluation dashboard, insights report and trace replay. The live "try your own ticket" box is rate-limited and capped per day.
- **Documentation:** the README opens with the one-line description and three headline numbers with confidence intervals, followed by the ML and ablation tables, a graph diagram, a statement of how data was simulated, a "Built AI-native" section and a video link. Major decisions are recorded as ADRs. CLAUDE.md is committed.
- **Build order:** data generation → triage pipeline → evaluation → insights → closing gaps and before-and-after → demo → README, ADRs and video.

## Testing Decisions

- **What makes a good test:** tests exercise external behavior through the public entry points (triage, evaluate, insights) and assert on their outputs: decisions, handoff packets, traces, metric values and report contents. They don't assert on internal node order, prompt wording or private helpers. Refactoring the graph internals shouldn't break tests unless behavior changes.
- **One seam:** the model gateway is the only thing substituted. Tests use the scripted fake gateway, with responses set per test, e.g. "classifier returns intent X at confidence 0.9" or "grounding check says yes". Everything else runs for real: the knowledge base and vector store, safety rules, the LangGraph pipeline, metric computation and clustering.
- **Triage tests:**
  - Safety rules escalate even when the fake model would auto-reply, e.g. a prescription-error ticket from a physician.
  - Retrieval-threshold failures escalate.
  - Grounding failures escalate.
  - Validation failures retry, then escalate.
  - A passing ticket auto-replies and cites its article.
  - Handoff packets contain every required field.
  - A trace record is written for every node.
- **Evaluation tests:** small hand-built fixtures with known correct answers. They cover the headline metric definitions (including that a wrong auto-reply isn't counted as deflection), confusion-matrix values, escalation recall, macro-F1, bootstrap intervals that contain the point estimate, a Cohen's kappa calculation on a known case, ablation switches changing the results, and the regression gate failing on unsafe auto-replies above 0 or a deflection drop.
- **Insights tests:** scripted embeddings forming clearly separated clusters. They check that the expected number of clusters is found, that ordering follows volume, and that each cluster section has a name, summary, example tickets, a gap-or-defect label and a recommended action.
- **Data generation tests (light):** check that labels exist before ticket text, the knowledge base covers only the intended subset of topics, the week split is respected, and every ticket has complete metadata.
- **Reproducibility test:** the full evaluation runs in CI against the committed cache with no API keys and reproduces the recorded numbers.
- **Not unit-tested:** the Streamlit demo, which only reads outputs the tested entry points produce.
- **Prior art:** none in this repo, which is new. The author's RAG Notes project is prior art for the retrieval and distance-threshold approach.

## Out of Scope

- Real patient data, real customer tickets, or integration with any real EHR, ticketing system or helpdesk (Zendesk, Salesforce and so on).
- Using any real company's name, branding or product as the fictional product.
- Multi-turn conversations, follow-up replies or reopened tickets.
- Sending real email or messages to anyone.
- A REST API service (FastAPI) or a Next.js frontend. The library and CLI come first, and an API can be added later.
- Hosted tracing services (Langfuse or LangSmith) beyond an optional future add-on.
- Fine-tuning or training models. Only prompting, retrieval and configuration.
- User authentication, multi-tenant support or role-based access in the demo.
- HIPAA or other compliance certification. The domain is simulated.

## Further Notes

- **Audience:** primarily hiring managers and engineers for AI/LLM application engineering roles. The fallback audience is bridge roles (support engineer, solutions or integration engineer, AI-first support teams). The project must not read as an application to any single company.
- **Honesty is the core design principle:** labels-first generation, time-based splits, thresholds tuned only on weeks 1–2, simulated (not planted-and-told) gaps, wrong auto-replies counted as failures, and judge agreement reported are all there so that every number survives a skeptical interviewer.
- **AI-native development is intended and should be visible:** use AI tools as much as possible, and document their role in the README's "Built AI-native" section.
- **Natural interview talking points:** the ablation table (what each safety layer contributes) and the before-and-after gap loop (an insight changing a decision).
