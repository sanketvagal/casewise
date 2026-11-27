# 05: Labels-first data generation

**What to build:** One command generates the fictional clinical SaaS world. It produces a product spec of about 40 support topics, then per-ticket labels, then ticket text written *from* those labels (about 400 tickets across weeks 1–2 and 3–4), and an initial knowledge base covering only about 25 of the topics. Generation uses a different model family (Gemini) from triage.

**Blocked by:** 01

**Status:** done

- [x] Gemini implementation added to the model gateway
- [x] The product spec covers scheduling, e-prescribing, lab orders and results, billing, and the patient portal for a fictional, unbranded product
- [x] Labels are generated before ticket text, and ticket text is generated from them
- [x] Each ticket has a subject, body, requester role (physician, front desk, biller, practice admin), practice size, plan tier and timestamp
- [x] Tickets vary in tone and level of detail
- [x] About 200 tickets in weeks 1–2 and about 200 in weeks 3–4, split by timestamp
- [x] The initial knowledge base covers about 25 of the 40 topics, and the uncovered topics are recorded for later scoring only, never shown to triage or insights
- [x] A share of tickets is must-escalate, matching the safety-rule categories
- [x] Generated data is committed, along with the cache that produced it
- [x] Tests (light): labels exist before text, knowledge-base coverage matches the intended topics, the week split holds, metadata is complete
- [x] ADR written for labels-first generation, the cross-family generator, and simulated gaps

## Comments

**2026-11-18 (agent):** These design choices were settled with the author before coding. ADR 6 records them.

- **Labels:** sampled in code with a seeded random generator (`sample_labels`), not by a model. The labels are written to `data/labels.jsonl` before any ticket text.
- **Gap intent:** each labeled ticket keeps its true `topic`. `intent` is the topic id when the topic is covered, and `other` when it isn't. Triage's label set stays at article ids plus `other`, so the gap names never leak. Issue 11 relabels intents for the topics it closes.
- **Rule tickets:** written from a plain-words situation, never from the rule's phrases. The generation report counts how many the keyword rules catch.
- **Generator:** `gemini-3.5-flash-lite`, with its own `generator_provider` and `generator_model` settings. The Gemini provider already existed from issue 04. This issue adds retries on 429/5xx for free-tier rate limits.

**2026-11-18 (agent):** Implemented test-first on branch `05-labels-first-data-generation`.

- **Interface:** `generate(gateway=, settings=, out_dir=, seed=) -> list[LabeledTicket]` and `casewise generate [--out data] [--seed 5]`.
- **Outputs:** `data/spec.json`, `labels.jsonl`, `tickets/weeks-1-2.jsonl`, `tickets/weeks-3-4.jsonl`, `kb/` (25 articles), `scoring/uncovered-topics.json` and `generation-report.md`.
- **Tests:** 12 tests in `tests/test_generate.py` drive `generate()` through `ScriptedGateway`, which now takes callable replies so a step can echo the ticket ids its prompt asks for.
  - Labels are on disk before the first ticket-text call.
  - Each ticket's text and metadata come from its own labels.
  - The knowledge base is exactly the covered topics.
  - Uncovered topics are labeled `other`, with no answering article, and must-escalate.
  - The two fortnights split by timestamp.
  - Metadata is complete.
  - Every safety rule has tickets, with the right areas and roles.
  - Tone and detail vary.
  - Replay from the cache regenerates identical files.
  - A spec that misses an area stops generation.
  - The CLI exits 1 on a cache miss.

  Three deliberate breaks were each caught: labels written after the text, gap topics leaking into `intent`, and timestamps drawn from the wrong fortnight. The suite has 85 tests.
- **Live run:** 70 Gemini calls in 4m19s (66 plus 4 validation retries). 40 topics over 6 areas, 25 covered. Weeks 1–2 have 87 must-escalate tickets out of 200 (40 rule, 47 no-answer). Weeks 3–4 have 103 (40 rule, 63 no-answer). Replay with no keys regenerated `data/` byte for byte.
- **Findings for issue 06** (from `data/generation-report.md`):
  - **6 of the 80 rule-situation tickets match no rule:** 2 `patient_data_exposure`, 3 `suspected_outage`, 1 `urgent_clinician`. If the LLM checks pass them, they are unsafe auto-replies.
  - **99 of the 320 routine tickets match a rule anyway:** 60 `prescription_error`, mostly routine e-prescribing how-tos containing "prescription"; 33 `patient_data_exposure`, likely "chart"; 5 `urgent_clinician`; 1 `suspected_outage`. These escalate and cap deflection.
  - Changing the rules is a separate decision with its own baseline.
- **Caveats:**
  - `kb_dir` still points at the three hand-written articles, so the issue 04 replay keeps working. Issue 06 switches it to `data/kb`. The only change to `eval/results/latest.json` is a `"topic": null` field on each row.
  - Generator and judge share Flash-Lite.
  - Four tickets mention "Visa" or "Mastercard" as card types. This is not product branding and was left as is.
