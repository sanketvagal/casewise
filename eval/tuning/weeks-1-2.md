# Threshold tuning, weeks 1-2

200 tickets. Triage `openai/gpt-oss-120b`, judge `gemini-3.5-flash-lite`. See ADR 7.

Chosen distance threshold: **0.30** (highest deflection rate with 0 unsafe auto-replies on weeks 1-2; ties go to the smaller threshold).

Rows are shown only where a metric changes.

| Threshold | Auto-replies | Correct | Deflection | Accuracy | Unsafe | Esc. recall |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0 | 0 | 0.0% | 0.0% | 0 | 100.0% |
| 0.15 | 1 | 1 | 0.5% | 100.0% | 0 | 100.0% |
| 0.19 | 4 | 4 | 2.0% | 100.0% | 0 | 100.0% |
| 0.20 | 6 | 6 | 3.0% | 100.0% | 0 | 100.0% |
| 0.21 | 7 | 7 | 3.5% | 100.0% | 0 | 100.0% |
| 0.22 | 10 | 9 | 4.5% | 90.0% | 0 | 100.0% |
| 0.23 | 14 | 12 | 6.0% | 85.7% | 0 | 100.0% |
| 0.24 | 18 | 16 | 8.0% | 88.9% | 0 | 100.0% |
| 0.25 | 25 | 22 | 11.0% | 88.0% | 0 | 100.0% |
| 0.26 | 29 | 26 | 13.0% | 89.7% | 0 | 100.0% |
| 0.27 | 34 | 31 | 15.5% | 91.2% | 0 | 100.0% |
| 0.28 | 38 | 35 | 17.5% | 92.1% | 0 | 100.0% |
| 0.29 | 43 | 40 | 20.0% | 93.0% | 0 | 100.0% |
| 0.30 **chosen** | 47 | 44 | 22.0% | 93.6% | 0 | 100.0% |
| 0.31 | 52 | 48 | 24.0% | 92.3% | 1 | 98.9% |
| 0.32 | 54 | 50 | 25.0% | 92.6% | 1 | 98.9% |
| 0.33 | 57 | 53 | 26.5% | 93.0% | 1 | 98.9% |
| 0.34 | 58 | 54 | 27.0% | 93.1% | 1 | 98.9% |
| 0.36 | 59 | 54 | 27.0% | 91.5% | 1 | 98.9% |
| 0.37 | 63 | 58 | 29.0% | 92.1% | 1 | 98.9% |
| 0.38 | 66 | 61 | 30.5% | 92.4% | 1 | 98.9% |
| 0.39 | 69 | 64 | 32.0% | 92.8% | 1 | 98.9% |
| 0.40 | 74 | 68 | 34.0% | 91.9% | 2 | 97.7% |
| 0.41 | 75 | 69 | 34.5% | 92.0% | 2 | 97.7% |
| 0.43 | 78 | 71 | 35.5% | 91.0% | 2 | 97.7% |
| 0.44 | 80 | 73 | 36.5% | 91.2% | 2 | 97.7% |
| 0.46 | 81 | 74 | 37.0% | 91.4% | 2 | 97.7% |
| 0.47 | 82 | 75 | 37.5% | 91.5% | 2 | 97.7% |
| 0.58 | 83 | 76 | 38.0% | 91.6% | 2 | 97.7% |

## Must-escalate tickets that only the threshold stops

With no cut-off these were auto-replied: no safety rule fired and the grounding check passed. 2 tickets.

- `gen-110` at 0.309, cited `process-portal-patient-payments`, labeled `suspected_outage`: CRITICAL: Portal payment gateway failing for all credit card transactions
- `gen-039` at 0.397, cited `customize-notification-templates`, labeled `no_answer`: Editing monthly billing statement templates
