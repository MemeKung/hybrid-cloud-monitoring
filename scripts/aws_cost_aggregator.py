#!/usr/bin/env python3
"""
AWS Cost Aggregator for Zabbix
--------------------------------
Pulls yesterday's AWS cost from Cost Explorer, grouped by service and by
EC2 instance type, then pushes the values into Zabbix as trapper items
via the zabbix_sender CLI.

Designed to run once a day via cron on the Zabbix Proxy host
(zabbix-proxy-aws), since AWS Cost Explorer data is updated daily, not
in real time.

Zabbix-side setup required (one-time, done in the Web UI):
  1. Host "AWS-Cost-Monitor" (monitored by proxy zabbix-proxy-aws)
  2. Item "aws.cost.total" - Zabbix trapper, Numeric (float), Units USD
  3. Discovery rule "aws.cost.discovery" - Zabbix trapper
  4. Item prototype "aws.cost.service[{#SERVICE}]" - Zabbix trapper,
     Numeric (float), Units USD, linked to the discovery rule above
"""

import boto3
import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ZABBIX_SENDER_BIN = "/usr/bin/zabbix_sender"
ZABBIX_SERVER = "127.0.0.1"     # Always send to the LOCAL proxy, never the
ZABBIX_PORT = "10051"           # on-prem Server's private IP (unreachable
ZABBIX_HOST = "AWS-Cost-Monitor"  # from a host on the public internet).

LOG_FILE = "/var/log/zabbix/aws_cost_aggregator.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def get_date_range():
    """Cost Explorer reports on whole days; use 'yesterday' since today's
    data is usually incomplete."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def fetch_cost_by_service(ce_client, start, end):
    """Returns {service_name: cost_float} for the given date range."""
    response = ce_client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    costs = {}
    for result in response["ResultsByTime"]:
        for group in result["Groups"]:
            service = group["Keys"][0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if amount > 0:  # skip zero-cost services to keep the LLD list small
                costs[service] = costs.get(service, 0.0) + amount
    return costs


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
    start, end = get_date_range()
    log.info("Fetching AWS cost for %s to %s", start, end)

    try:
        ce_client = boto3.client("ce")
        costs_by_service = fetch_cost_by_service(ce_client, start, end)
    except Exception as exc:
        log.error("Failed to fetch cost data from AWS: %s", exc)
        sys.exit(1)

    total_cost = sum(costs_by_service.values())
    log.info("Total cost: $%.4f across %d services", total_cost, len(costs_by_service))

    lines = [f"{ZABBIX_HOST} aws.cost.total {total_cost:.6f}"]

    # --- Low-level discovery payload: tell Zabbix which services exist ---
    discovery_data = {
        "data": [
            {"{#SERVICE}": build_zabbix_key_safe_name(service)}
            for service in costs_by_service
        ]
    }
    discovery_json = json.dumps(discovery_data)
    lines.append(f'{ZABBIX_HOST} aws.cost.discovery {discovery_json}')

    # --- Per-service cost values (item prototypes created via the LLD rule) ---
    for service, amount in costs_by_service.items():
        safe_service = build_zabbix_key_safe_name(service)
        lines.append(f'{ZABBIX_HOST} "aws.cost.service[{safe_service}]" {amount:.6f}')

    ok = send_to_zabbix(lines)
    if not ok:
        sys.exit(1)

    log.info("Successfully sent %d metrics to Zabbix", len(lines))


if __name__ == "__main__":
    main()
