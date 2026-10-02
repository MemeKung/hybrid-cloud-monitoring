# 06 — Grafana Dashboards

Dashboard JSON exports live in [`../grafana/`](../grafana/). All were built against **Grafana v13 (dashboard schema v2)** with the `alexanderzobnin-zabbix-datasource` plugin.

## 1. Install Grafana

```bash
sudo apt install -y apt-transport-https software-properties-common wget
sudo mkdir -p /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
sudo chmod 644 /etc/apt/keyrings/grafana.asc
echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
sudo apt update && sudo apt install -y grafana
sudo systemctl enable --now grafana-server
```
Open `http://<host>:3000`, log in `admin`/`admin`, change the password.

## 2. Connect Grafana to Zabbix

```bash
sudo grafana cli plugins install alexanderzobnin-zabbix-app
sudo systemctl restart grafana-server
```
Enable the app under **Apps**, then **Connections → Data sources → Add data source → Zabbix**:
- URL: `http://<zabbix-server-ip>/zabbix/api_jsonrpc.php` (note the `/zabbix/` path)
- Authentication: **Token** — create one in Zabbix (**Users → API tokens**) for a dedicated read-only user

### Zabbix permission gotcha

Zabbix permissions are granted at the **User Group** level, not the individual user. A user's own "Permissions" tab in the Web UI is really just a shortcut into their group's settings. If a Grafana panel shows "No data" even though `Monitoring → Latest data` has values, check **Users → User groups → (the group) → Host permissions** covers the relevant host group(s) with Read access — and make sure the user's Role is **User role**, not **Guest role** (Guest role disables API access outright).

## 3. Dashboards in this repo

| File | What it shows |
|---|---|
| `Hybrid_Cloud_Executive_Overview.json` | **The one to lead a demo with.** Single page, 9 panels: live status strip for all 3 environments, a dual-axis "Cost vs Performance" hero panel, Cost Breakdown bar gauges for AWS/GCP, and combined CPU/Memory/Network timeseries panels with one line per environment (AWS/GCP/On-Prem) |
| `Hybrid_Cloud_Cost_and_Performance_Dashboard.json` | Cost-focused view, AWS + GCP side by side |
| `ec2-target-01.json` / `gcp-target-01.json` / `Zabbix_Agent_On_Prem.json` | Per-host deep-dive dashboards (disk, network, load average, zombie processes, uptime) — drill-down views behind the Executive Overview |

Import via **Dashboards → Import → Upload dashboard JSON file**, pick the Zabbix data source when prompted.

### If multi-host panels show overlapping/ambiguous legend labels

When one panel queries the same item name from several different hosts (e.g. "CPU utilization" from AWS + GCP + On-Prem in one timeseries), Grafana may not auto-disambiguate the legend. Fix with a field override matched **by query ref ID** (`byFrameRefID`) rather than by series name, setting a `displayName` per query — this works regardless of what the raw series name happens to be.

## 4. Important caveat for live demos

Performance panels (CPU/Memory/Network) react within 1-2 minutes of real load. **Cost panels will not react live** — AWS Cost Explorer has roughly a 24h reporting delay, and Burstable instance types (t3/e2 families) don't bill extra for higher CPU unless "Unlimited" credit mode is explicitly enabled. Frame this as a demonstration of accurate cloud billing behavior, not a shortcoming of the dashboard.

## Known issues & fixes

| Symptom | Cause | Fix |
|---|---|---|
| Dashboard import fails: `DashboardSpec.timeSettings.weekStart: Invalid value: conflicting values ...` | An empty string `weekStart: ""` in the JSON — this schema version rejects it | Remove the `weekStart` key entirely (omit, don't set empty) |
| Import fails with a generic validation error referencing `apiVersion` | Wrong API version string in the JSON header | Use `dashboard.grafana.app/v2` (check what a real export from your own Grafana instance uses if this ever changes) |
