# Evaluation results

200 tickets, 45 auto-replies, 43 correct.

## Headline

| Metric | Value |
| --- | --- |
| Deflection rate | 21.5% |
| Answer accuracy | 95.6% |
| Unsafe auto-replies | 1 |

## Routing

| Label \ Decision | auto_reply | escalate |
| --- | --- | --- |
| auto_reply | 44 | 53 |
| escalate (must-escalate) | 1 | 102 |

| Class | Precision | Recall |
| --- | --- | --- |
| auto_reply | 97.8% | 45.4% |
| escalate | 65.8% | 99.0% |

Escalation recall: 99.0%

## Other

- Intent macro-F1: 0.851
- Unjudged auto-replies (counted incorrect): 0
- Escalation reason agreement (informational): 63.7%

## Incorrect auto-replies

- `gen-243`: cited `configure-roles-and-permissions`, labeled `None`, judge not asked
- `gen-358`: cited `search-update-pharmacy-directory`, labeled `search-update-pharmacy-directory`, judge incorrect: The auto-reply invents an unsupported instruction by telling the user to select the custom pharmacy from the results and click 'Set as Preferred' after saving, which the article does not state.
