#!/usr/bin/env python3
"""
GCP Cost Aggregator for Zabbix
--------------------------------
Reads yesterday's GCP cost from the BigQuery Billing Export table,
grouped by service, then pushes the values into Zabbix as trapper
items via the zabbix_sender CLI — mirrors aws_cost_aggregator.py so
both clouds report through the same pattern (Zabbix Trapper + LLD).

Unlike AWS Cost Explorer, GCP has no direct "get cost by date range"
API. The documented approach is to export Cloud Billing data to
BigQuery and query that table — this script assumes that export is
already configured (Billing export table backfills going forward
only, so allow 24-48h after enabling it before data appears).

Designed to run once a day via cron on the Zabbix Proxy host
(zabbix-proxy-gcp). Uses Application Default Credentials from the
VM's attached service account (zabbix-billing-reader) — no JSON key
needed, since GCP now blocks key creation by org policy on this
account by default.

Zabbix-side setup required (one-time, in the Web UI):
  1. Host "GCP-Cost-Monitor" (Host group: Cost Monitoring, monitored
     by proxy zabbix-proxy-gcp)
  2. Item "gcp.cost.total" - Zabbix trapper, Numeric (float), Units USD
  3. Discovery rule "gcp.cost.discovery" - Zabbix trapper
  4. Item prototype "gcp.cost.service[{#SERVICE}]" - Zabbix trapper,
     Numeric (float), Units USD, linked to the discovery rule above
"""

import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

from google.cloud import bigquery

# ---------------------------------------------------------------------------
# Configuration - EDIT THESE THREE VALUES to match your project/dataset/table
# ---------------------------------------------------------------------------
BQ_PROJECT = "capstone-zabbix-gcp"                          # your GCP project ID
BQ_DATASET = "billing_export"                                 # dataset created in Part A
BQ_TABLE = "gcp_billing_export_resource_v1_01E31A_64EC87_C5F478"  # exact table name from BigQuery Explorer

ZABBIX_SENDER_BIN = "/usr/bin/zabbix_sender"
ZABBIX_SERVER = "127.0.0.1"      # always the LOCAL proxy - same reasoning as the AWS
ZABBIX_PORT = "10051"            # script: the on-prem Server's private IP is unreachable
ZABBIX_HOST = "GCP-Cost-Monitor"  # from a VM on the public internet.

LOG_FILE = "/var/log/zabbix/gcp_cost_aggregator.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    force=True,  # google-cloud-bigquery configures a root logging handler on
                 # import, which makes basicConfig() a no-op without this —
                 # without force=True, nothing ever gets written to LOG_FILE.
)
log = logging.getLogger(__name__)


def fetch_cost_by_service():
    """Query yesterday's cost from the BigQuery billing export, grouped by service.

    Uses Application Default Credentials - on this VM that resolves to the
    attached service account automatically, no key file involved.
    """
    client = bigquery.Client(project=BQ_PROJECT)
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

    query = f"""
        SELECT
          service.description AS service_name,
          SUM(cost) AS total_cost
        FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
        WHERE DATE(usage_start_time) = @target_date
        GROUP BY service_name
        HAVING total_cost > 0
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("target_date", "DATE", yesterday)]
    )
    rows = client.query(query, job_config=job_config).result()

    costs = {}
    for row in rows:
        costs[row.service_name] = float(row.total_cost)
    return costs, yesterday


def build_zabbix_key_safe_name(name):
    """Zabbix item key parameters can't contain some characters; keep it simple."""
    return name.replace("[", "(").replace("]", ")").replace('"', "'")


def send_to_zabbix(lines):
    """Writes lines to a temp file in zabbix_sender bulk format and sends
    them all in a single call. Each line: '<host> <key> <value>'."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for line in lines:
            f.write(line + "\n")
        temp_path = f.name

    cmd = [
        ZABBIX_SENDER_BIN,
        "-z", ZABBIX_SERVER,
        "-p", ZABBIX_PORT,
        "-i", temp_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    log.info("zabbix_sender output: %s", result.stdout.strip())
    if result.returncode != 0:
        log.error("zabbix_sender failed (rc=%s): %s", result.returncode, result.stderr.strip())
        return False
    return True


def main():
    try:
        costs_by_service, target_date = fetch_cost_by_service()
    except Exception as exc:
        log.error("Failed to fetch cost data from BigQuery: %s", exc)
        sys.exit(1)

    total_cost = sum(costs_by_service.values())
    log.info(
        "Fetched GCP cost for %s: $%.4f across %d services",
        target_date, total_cost, len(costs_by_service),
    )

    lines = [f"{ZABBIX_HOST} gcp.cost.total {total_cost:.6f}"]

    # --- Low-level discovery payload: tell Zabbix which services exist ---
    discovery_data = {
        "data": [
            {"{#SERVICE}": build_zabbix_key_safe_name(service)}
            for service in costs_by_service
        ]
    }
    lines.append(f"{ZABBIX_HOST} gcp.cost.discovery {json.dumps(discovery_data)}")

    # --- Per-service cost values (item prototypes created via the LLD rule) ---
    for service, amount in costs_by_service.items():
        safe_service = build_zabbix_key_safe_name(service)
        lines.append(f'{ZABBIX_HOST} "gcp.cost.service[{safe_service}]" {amount:.6f}')

    if not send_to_zabbix(lines):
        sys.exit(1)

    log.info("Successfully sent %d metrics to Zabbix", len(lines))


if __name__ == "__main__":
    main()
