# 04 — Cost Visibility Layer

Scripts referenced here live in [`../scripts/`](../scripts/).

AWS and GCP expose billing data very differently — this is the main reason the two scripts look structurally similar (same LLD-trapper pattern feeding Zabbix) but pull data through completely different APIs.

## AWS: Cost Explorer API

1. Enable Cost Explorer (Billing console)
2. Create an IAM policy with `ce:GetCostAndUsage`, `ce:GetCostForecast`, `ce:GetDimensionValues`, attach to the proxy's IAM user/role
3. On `zabbix-proxy-aws`: `pip3 install boto3 --break-system-packages`, configure `~/.aws/credentials` with an access key
4. Deploy [`aws_cost_aggregator.py`](../scripts/aws_cost_aggregator.py) — it queries yesterday's cost grouped by AWS Service, then uses **Zabbix Low-Level Discovery over the trapper protocol**: it sends a discovery JSON (`{#SERVICE}` macro) *and* the cost values in the same run, so new AWS services automatically get their own Zabbix item with zero manual configuration.

## GCP: BigQuery Billing Export

GCP has **no direct equivalent of Cost Explorer**. The documented path is: export Cloud Billing data to BigQuery, then query that table with SQL.

1. Enable the BigQuery API, create a dataset (e.g. `billing_export`)
2. Billing → Billing export → BigQuery export → point it at that dataset
3. **Wait 24-48h** after enabling before the export table actually contains rows — there is no historical backfill
4. Grant the proxy's service account `BigQuery Data Viewer` + `BigQuery Job User` on the project holding the dataset
5. On `zabbix-proxy-gcp`: `pip3 install google-cloud-bigquery --break-system-packages`
6. Deploy [`gcp_cost_aggregator.py`](../scripts/gcp_cost_aggregator.py), filling in `BQ_PROJECT`, `BQ_DATASET`, `BQ_TABLE` (the exact exported table name, found in the BigQuery Explorer under your dataset — note it may be named `..._export_resource_v1_...` if you enabled "Detailed usage cost" export)

## Zabbix-side setup (identical pattern for both clouds)

| | AWS | GCP |
|---|---|---|
| Host | `AWS-Cost-Monitor` | `GCP-Cost-Monitor` |
| Host group | `Cost Monitoring` (same group for both) | `Cost Monitoring` |
| Monitored by proxy | `zabbix-proxy-aws` | `zabbix-proxy-gcp` |
| Total cost item | `aws.cost.total` (Zabbix trapper, float, USD) | `gcp.cost.total` |
| Discovery rule | `aws.cost.discovery` (Zabbix trapper) | `gcp.cost.discovery` |
| Item prototype | `aws.cost.service[{#SERVICE}]` | `gcp.cost.service[{#SERVICE}]` |

Item **Name** fields must read exactly `AWS Total Daily Cost` / `GCP Total Daily Cost` and `AWS Cost - {#SERVICE}` / `GCP Cost - {#SERVICE}` — the Grafana dashboards in `../grafana/` filter on these names.

## Cron (on each respective proxy)

```bash
sudo touch /var/log/zabbix/aws_cost_aggregator.log   # or gcp_...
sudo chown $USER:$USER /var/log/zabbix/aws_cost_aggregator.log
crontab -e
```
```
0 1 * * * /usr/bin/python3 /home/<user>/aws_cost_aggregator.py   # on the AWS proxy
0 2 * * * /usr/bin/python3 /home/<user>/gcp_cost_aggregator.py   # on the GCP proxy
```

## Daily digest (optional, combines both clouds into one message)

[`daily_cost_digest.py`](../scripts/daily_cost_digest.py) runs on the **Zabbix Server** (not a proxy) after both cron jobs above have completed. It reads the latest `aws.cost.total` / `gcp.cost.total` values via the **Zabbix API** and broadcasts one combined summary over LINE — see `05-alerting.md` for the LINE side. Needs a dedicated Zabbix API token (Users → API tokens) for a read-only user.

```
0 3 * * * /usr/bin/python3 /home/<user>/daily_cost_digest.py
```

> Note the script reports **yesterday's** cost (cloud billing APIs aren't same-day accurate), so the date label in the message is computed as `today - 1 day`, not the run date.

## Known issues & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `zabbix_sender` reports `failed: N` | Host/Item/Discovery rule not created in Zabbix yet, or Item **Name** doesn't match what the dashboard queries for | Create the Zabbix-side objects first (table above) before running the script |
| `zabbix_sender` works but Grafana panel shows "No data" even though Zabbix Latest Data has a value | Item's **History storage period** set to "Do not keep history", or the Grafana API user's Host permissions don't cover the `Cost Monitoring` group | Set history to e.g. `31d`; grant Host permissions at the **User Group** level (Zabbix scopes permissions there, not per-user) |
| Script log file never gets written even though the script exits 0 | `google-cloud-bigquery` (or similar libs) pre-configure Python's root logger on import, so `logging.basicConfig()` becomes a silent no-op | Pass `force=True` to `logging.basicConfig()` |
| `404 Not Found` calling the Zabbix API | Missing the `/zabbix/` path segment — the frontend may be installed under that subpath | Use `http://<server-ip>/zabbix/api_jsonrpc.php`, not `http://<server-ip>/api_jsonrpc.php` |
