#!/usr/bin/env python3
"""
Daily Cost Digest — AWS + GCP combined
-----------------------------------------
Runs once a day on the Zabbix Server (172.16.46.104), AFTER both
aws_cost_aggregator.py (runs 01:00 on zabbix-proxy-aws) and
gcp_cost_aggregator.py (runs 02:00 on zabbix-proxy-gcp) have pushed
their values into Zabbix.

Reads the latest aws.cost.total / gcp.cost.total item values via the
Zabbix API, combines them into one message, and broadcasts it via the
LINE Messaging API — every day, regardless of whether cost crosses any
threshold. This is a scheduled report, not a Zabbix Trigger-based
alert, so it does not touch the existing Trigger Action from Phase 5.

Recommended cron (on Zabbix Server): 0 3 * * *
"""

import json
import logging
from datetime import datetime, timedelta, timezone

import requests

# ---------------------------------------------------------------------------
# Configuration — EDIT THESE TWO VALUES
# ---------------------------------------------------------------------------
ZABBIX_URL = "http://172.16.46.104/api_jsonrpc.php"
ZABBIX_API_TOKEN = "PASTE_ZABBIX_API_TOKEN_HERE"

LINE_CHANNEL_ACCESS_TOKEN = "PASTE_LINE_CHANNEL_ACCESS_TOKEN_HERE"
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"

BANGKOK_TZ = timezone(timedelta(hours=7))
LOG_FILE = "/var/log/zabbix/daily_cost_digest.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    force=True,  # see aws_cost_aggregator.py for why this is needed
)
log = logging.getLogger(__name__)


def zbx_call(method: str, params: dict):
    headers = {
        "Content-Type": "application/json-rpc",
        "Authorization": f"Bearer {ZABBIX_API_TOKEN}",
    }
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    resp = requests.post(ZABBIX_URL, headers=headers, data=json.dumps(payload), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Zabbix API error calling {method}: {data['error']}")
    return data["result"]


def get_latest_cost(host_name: str, item_key: str):
    """Returns (value, last_updated_utc) for the given host/item key."""
    hosts = zbx_call("host.get", {"filter": {"host": [host_name]}, "output": ["hostid"]})
    if not hosts:
        raise RuntimeError(f"Host '{host_name}' not found in Zabbix")
    hostid = hosts[0]["hostid"]

    items = zbx_call("item.get", {
        "hostids": [hostid],
        "filter": {"key_": item_key},
        "output": ["lastvalue", "lastclock"],
    })
    if not items:
        raise RuntimeError(f"Item '{item_key}' not found on host '{host_name}'")
    if not items[0]["lastclock"] or items[0]["lastclock"] == "0":
        raise RuntimeError(f"Item '{item_key}' on '{host_name}' has no data yet")

    value = float(items[0]["lastvalue"])
    last_updated = datetime.fromtimestamp(int(items[0]["lastclock"]), tz=timezone.utc)
    return value, last_updated


def send_line_broadcast(message: str):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {"messages": [{"type": "text", "text": message}]}
    resp = requests.post(LINE_BROADCAST_URL, headers=headers, data=json.dumps(payload), timeout=10)
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"LINE broadcast failed: HTTP {resp.status_code}: {resp.text}")


def main():
    today_str = datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d")

    try:
        aws_cost, aws_updated = get_latest_cost("AWS-Cost-Monitor", "aws.cost.total")
    except Exception as exc:
        log.error("Failed to read AWS cost: %s", exc)
        raise

    try:
        gcp_cost, gcp_updated = get_latest_cost("GCP-Cost-Monitor", "gcp.cost.total")
    except Exception as exc:
        log.error("Failed to read GCP cost: %s", exc)
        raise

    total = aws_cost + gcp_cost

    message = (
        "\U0001F4CA Hybrid Cloud Daily Cost Summary\n"
        f"\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48: {today_str}\n"
        "\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\n"
        f"\u2601\ufe0f AWS: ${aws_cost:,.4f}\n"
        f"\u2601\ufe0f GCP: ${gcp_cost:,.4f}\n"
        "\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\n"
        f"\U0001F4B0 \u0e23\u0e27\u0e21: ${total:,.4f}\n\n"
        f"(\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e25\u0e48\u0e32\u0e2a\u0e38\u0e14 AWS: {aws_updated.strftime('%H:%M UTC')}, "
        f"GCP: {gcp_updated.strftime('%H:%M UTC')})"
    )

    try:
        send_line_broadcast(message)
    except Exception as exc:
        log.error("Failed to send LINE broadcast: %s", exc)
        raise

    log.info(
        "Sent daily cost digest: AWS=$%.4f GCP=$%.4f Total=$%.4f",
        aws_cost, gcp_cost, total,
    )


if __name__ == "__main__":
    main()
