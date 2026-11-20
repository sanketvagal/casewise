# Generation report

Seed 5. Ticket text, articles and topics written by `gemini-3.5-flash-lite`; labels sampled in code before any text. See ADR 6.

40 topics, 25 covered by the initial knowledge base.

| | weeks 1-2 | weeks 3-4 |
|---|---:|---:|
| Tickets | 200 | 200 |
| Must-escalate | 87 | 103 |
|   for a safety rule | 40 | 40 |
|   no answer (uncovered topic) | 47 | 63 |
| Not must-escalate | 113 | 97 |

## Do the keyword safety rules catch the rule-labeled tickets?

Rule tickets were written from a situation, not from the rule's phrases.

| Rule | Labeled | Caught by that rule | Caught by any rule |
|---|---:|---:|---:|
| `patient_data_exposure` | 16 | 14 | 14 |
| `prescription_error` | 16 | 16 | 16 |
| `billing_dispute` | 16 | 16 | 16 |
| `suspected_outage` | 16 | 11 | 13 |
| `urgent_clinician` | 16 | 15 | 15 |

## Tickets with no rule situation that a rule fires on anyway

99 of 320. Triage will escalate these: a cost to deflection, not a safety problem.

- `patient_data_exposure`: 33
- `prescription_error`: 60
- `suspected_outage`: 1
- `urgent_clinician`: 5
