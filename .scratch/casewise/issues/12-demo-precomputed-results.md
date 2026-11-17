# 12: Demo with precomputed results

**What to build:** A Streamlit app a reviewer can explore instantly at no cost. It includes an evaluation dashboard (headline numbers with confidence intervals, ML table, and the ablation, model-comparison and before-and-after tables where those results exist), the weekly insights report, and a trace replay view that steps through the graph's decisions for any evaluated ticket.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] The app reads only committed results, traces and reports, and makes no model calls
- [ ] Evaluation dashboard with headline numbers, confidence intervals, confusion matrix and ML metrics
- [ ] The ablation, model comparison and before-and-after sections appear once their results exist
- [ ] The insights report is shown
- [ ] Trace replay: pick a ticket and see each step's input, output, decision and the final outcome with its handoff packet
- [ ] Works locally with a single command
