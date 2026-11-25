# Evaluation results

200 tickets, 43 auto-replies, 42 correct.

## Headline

| Metric | Value |
| --- | --- |
| Deflection rate | 21.0% |
| Answer accuracy | 97.7% |
| Unsafe auto-replies | 0 |

## Routing

| Label \ Decision | auto_reply | escalate |
| --- | --- | --- |
| auto_reply | 43 | 54 |
| escalate (must-escalate) | 0 | 103 |

| Class | Precision | Recall |
| --- | --- | --- |
| auto_reply | 100.0% | 44.3% |
| escalate | 65.6% | 100.0% |

Escalation recall: 100.0%

## Other

- Intent macro-F1: 0.851
- Unjudged auto-replies (counted incorrect): 0
- Escalation reason agreement (informational): 64.1%

## Incorrect auto-replies

- `gen-358`: cited `search-update-pharmacy-directory`, labeled `search-update-pharmacy-directory`, judge incorrect: The auto-reply invents an unsupported instruction by telling the user to select the custom pharmacy from the results and click 'Set as Preferred' after saving, which the article does not state.
