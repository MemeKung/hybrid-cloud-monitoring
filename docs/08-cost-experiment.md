# 08 — Cloud Cost Experiment

A controlled experiment comparing how AWS and GCP cost and *report* cost in response to the same action — turns the Cost Visibility Layer from "a dashboard that shows numbers" into "a tool used to answer a real comparative question". Full protocol and results template are in [`../planning-docs/`](../planning-docs/):

- `Cost_Test_Case_Protocol.docx` — three candidate test cases (Compute resize, Storage add, Network egress), a pre-test safety checklist, step-by-step procedure, and a rollback plan for each
- `cost_test_case_results.xlsx` — a results log with formulas (Duration / Cost Delta / Detection Latency auto-computed) and a Comparison Summary sheet that aggregates AWS vs GCP automatically once the log is filled in

## Why this exists as a separate phase

It measures two independent things worth comparing explicitly:
1. **Magnitude** — how much did cost increase for the same action on each cloud
2. **Latency** — how long before each cloud's billing pipeline actually reported it (this project's own experience already shows GCP's BigQuery-export path lags AWS's Cost Explorer meaningfully — see `04-cost-visibility-layer.md`)

## Recommended test case to run first

**TC-A: Compute Resize** — resize both target instances from micro → small for exactly 1 hour, then revert. It's the easiest to control and reverse, and compute is the dominant cost driver for both clouds in this project's setup. See the protocol doc for the full step-by-step and the safety checklist (budget alerts, rollback plan, a fixed end time) that should be satisfied before running *any* of the three test cases — they all intentionally spend real money.
