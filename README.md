# Hybrid Cloud Infrastructure Monitoring Dashboard

A unified monitoring system built on **Zabbix 7.0** + **Grafana** that watches on-premise servers, AWS, and GCP in one place — with a Cost Visibility Layer that pulls real billing data from both clouds into the same dashboards used for performance monitoring.

Capstone project, Computer Engineering. This repository contains every script, dashboard export, and configuration file produced during the project, plus step-by-step setup guides detailed enough to reproduce the whole system from zero.

---

## Architecture

```
                         ┌───────────────────────────┐
                         │   Grafana (visualization)  │
                         │  Cost + Performance panels  │
                         └──────────────┬──────────────┘
                                        │ Zabbix API
                         ┌──────────────▼──────────────┐
                         │   Zabbix Server + MariaDB    │
                         │        (on-premise)          │
                         └───┬───────────────────┬──────┘
                   Passive   │                   │  Passive
                   (PSK)     │                   │  (PSK)
                 ┌───────────▼─────┐   ┌─────────▼──────────┐
                 │ Zabbix Proxy    │   │ Zabbix Proxy        │
                 │ (AWS, us-east-1)│   │ (GCP, us-central1)  │
                 └───┬─────────────┘   └──────────┬──────────┘
                     │                             │
            ┌────────▼────────┐          ┌─────────▼─────────┐
            │ EC2 target(s)   │          │ Compute Engine     │
            │ + Agent 2       │          │ target(s) + Agent 2│
            └─────────────────┘          └─────────────────────┘

   On-prem Agent ──────────────────────────────────► Zabbix Server (direct)

   AWS Cost Explorer ──┐                        ┌── GCP BigQuery Billing Export
                        ▼                        ▼
              aws_cost_aggregator.py   gcp_cost_aggregator.py
                        │                        │
                        └──────► Zabbix (Trapper + LLD) ◄──────┘
                                        │
                              daily_cost_digest.py ──► LINE (daily summary)
                              Zabbix Trigger Action ──► LINE (real-time alerts)
```

**Why Zabbix Proxies run in Passive mode:** the on-prem Zabbix Server sits behind a private/NATed IP with no port-forwarding (the normal case for a lab/university network), so cloud Proxies can never successfully dial *out* to it (Active mode). Passive mode flips that — the Server dials out to each Proxy instead, which works because the Server's own network allows outbound connections. See `docs/02-aws-setup.md` for the full story.

---

## Repository structure

```
.
├── docs/                      — step-by-step setup guides, one per phase
│   ├── 01-onprem-setup.md
│   ├── 02-aws-setup.md
│   ├── 03-gcp-setup.md
│   ├── 04-cost-visibility-layer.md
│   ├── 05-alerting.md
│   ├── 06-dashboards.md
│   ├── 07-load-testing.md
│   └── 08-cost-experiment.md
├── scripts/                   — Python automation
│   ├── aws_cost_aggregator.py
│   ├── gcp_cost_aggregator.py
│   ├── daily_cost_digest.py
│   └── cpu_load_app.py
├── grafana/                    — dashboard JSON exports, ready to import
│   ├── Hybrid_Cloud_Executive_Overview.json      ← start here for a demo
│   ├── Hybrid_Cloud_Cost_and_Performance_Dashboard.json
│   ├── ec2-target-01.json
│   ├── gcp-target-01.json
│   └── Zabbix_Agent_On_Prem.json
├── load-testing/
│   └── hybrid_cloud_load_test.jmx
├── config/
│   └── zabbix_config_reference.md   — every .conf file used, in one place
└── planning-docs/               — original project planning deliverables
    ├── 1.1_System_Architecture_Document.pdf
    ├── 1.2_Technology_Stack_Justification.pdf
    ├── 1.3_Network_Design_Document.pdf
    ├── 1.4_Project_Plan_Gantt.xlsx
    ├── 1.4_Project_Plan_RiskRegister.docx
    ├── Cost_Test_Case_Protocol.docx
    └── cost_test_case_results.xlsx
```

---

## Prerequisites

- An Ubuntu 22.04/24.04 host (or VM) for the Zabbix Server — this guide uses `172.16.46.104` as the example IP throughout, substitute your own
- AWS account + GCP account (both have a free tier sufficient for this whole project — see the budget-alert setup in the AWS/GCP guides, it matters)
- A LINE account, for the alerting channel
- Python 3.10+ on every host that runs one of the scripts in `scripts/`
- Grafana 11+ with the `alexanderzobnin-zabbix-datasource` plugin
- (Optional, for live demos) Apache JMeter + Java

---

## Setup order

Follow these in order — each later step assumes the previous ones are working.

1. **[`docs/01-onprem-setup.md`](docs/01-onprem-setup.md)** — Zabbix Server, MariaDB, the on-prem Agent, and the `Custom Linux Extended` template (adds Zombie Process + Agent Availability monitoring, not in Zabbix's stock templates)
2. **[`docs/02-aws-setup.md`](docs/02-aws-setup.md)** — VPC, Security Groups, Zabbix Proxy, a target EC2 instance, Auto-Discovery
3. **[`docs/03-gcp-setup.md`](docs/03-gcp-setup.md)** — same shape as AWS, with GCP-specific gotchas (Always Free region/instance-count/disk-type limits, Service Account key policy, IAP firewall rule)
4. **[`docs/04-cost-visibility-layer.md`](docs/04-cost-visibility-layer.md)** — AWS Cost Explorer + GCP BigQuery Billing Export → Zabbix, via `scripts/aws_cost_aggregator.py` / `scripts/gcp_cost_aggregator.py`
5. **[`docs/05-alerting.md`](docs/05-alerting.md)** — LINE Messaging API, a Zabbix Webhook Media Type, and a Trigger Action designed to auto-cover any host added later by Auto-Discovery
6. **[`docs/06-dashboards.md`](docs/06-dashboards.md)** — Grafana install + the 5 dashboards in `grafana/`
7. **[`docs/07-load-testing.md`](docs/07-load-testing.md)** — optional, for making Performance panels move live during a demo
8. **[`docs/08-cost-experiment.md`](docs/08-cost-experiment.md)** — optional, a controlled experiment comparing AWS vs GCP cost behavior using the layer built in step 4

Each guide has a **Known issues & fixes** table at the bottom covering the real problems hit while building this (wrong Zabbix API path, dashboard schema validation errors, silent logging bugs, IAM scoping across GCP projects, and more) — worth reading even if your setup "should" work, since several of these fail silently.

---

## Credentials — nothing in this repo is a real secret

Every script and config file here uses placeholder values (`PASTE_..._HERE`, example IPs, etc.). Before deploying:
- Fill in your own AWS Access Key / GCP Service Account / LINE Channel Access Token / Zabbix API Token directly on the target host, **not** in a copy of these files that gets committed back
- If you fork this repo, double-check `scripts/*.py` and `config/zabbix_config_reference.md` for any IP addresses or identifiers specific to the original deployment and swap them for your own

---

## License

Academic capstone project. Reuse for learning purposes is welcome — no warranty of any kind, this was built and documented by a student, not a vendor.
