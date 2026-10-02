"""
CPU Load Generator — for JMeter demo purposes
------------------------------------------------
Deploy this on ec2-target-01 / gcp-target-01. Every hit to /load burns
CPU for a few seconds (SHA-256 hashing in a tight loop), which shows up
immediately in the "CPU utilization" item Zabbix Agent already collects
on this host — no new Zabbix configuration needed, it's the same item
the existing dashboards already graph.

Run with: python3 app.py
Listens on: 0.0.0.0:5000
"""

from flask import Flask, jsonify, request
import hashlib
import time

app = Flask(__name__)


def burn_cpu(duration_seconds: float) -> int:
    """Keeps a core busy hashing for roughly `duration_seconds`."""
    end_time = time.time() + duration_seconds
    counter = 0
    payload = b"zabbix-jmeter-load-test"
    while time.time() < end_time:
        hashlib.sha256(payload + str(counter).encode()).hexdigest()
        counter += 1
    return counter


@app.route("/")
def health():
    """Quick check that the app is up before pointing JMeter at it."""
    return jsonify({"status": "ok", "message": "CPU load generator is running"})


@app.route("/load")
def load():
    """Each hit burns CPU for `seconds` (default 2). JMeter hitting this
    with many concurrent threads is what pushes CPU utilization up."""
    seconds = float(request.args.get("seconds", 2))
    seconds = max(0.1, min(seconds, 10))  # clamp to a sane range
    iterations = burn_cpu(seconds)
    return jsonify({"status": "done", "seconds": seconds, "iterations": iterations})


if __name__ == "__main__":
    # threaded=True lets multiple concurrent JMeter requests actually run
    # in parallel instead of queueing one at a time.
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
