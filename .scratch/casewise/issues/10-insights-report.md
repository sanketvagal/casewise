# 10: Insights report

**What to build:** `casewise insights` turns escalated weeks 1–2 tickets into a weekly Markdown report for Product and Engineering. Clusters are ordered by volume. Each has a name, a summary, example tickets, a label (likely knowledge-base gap or product defect), and a recommended action. A separate score (not shown in the report) says how many of the simulated knowledge-base gaps were found.

**Blocked by:** 02, 03, 05

**Status:** ready-for-agent

- [ ] Escalated tickets are embedded through the gateway and clustered with HDBSCAN, with no preset number of clusters
- [ ] An LLM names and summarizes each cluster, labels it as a gap or a defect, and recommends an action (structured output)
- [ ] The report is ordered by cluster volume and includes example tickets
- [ ] Runs only on weeks 1–2
- [ ] A separate score compares the gap clusters found against the recorded uncovered topics
- [ ] Tests: scripted embeddings forming separated clusters produce the expected clusters, ordered by volume, and every section has all required parts
- [ ] ADR written for the clustering approach and report format
