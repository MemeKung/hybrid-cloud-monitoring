# 07 — JMeter Load Testing (for live demos)

Goal: make the Performance panels visibly react during a demo by generating real CPU load on all three target hosts simultaneously.

Zabbix has no endpoint JMeter can hit directly to *create* load — Agents only report metrics, they don't accept work. The pattern used here: deploy a small Flask app on each target host with a CPU-burning endpoint, then have JMeter hit that endpoint concurrently. The resulting CPU usage is picked up by the **same** `CPU utilization` item the dashboards already graph — no Zabbix-side changes needed.

```
JMeter (your machine) → HTTP GET /load → Flask app (on each VM) → burns CPU
                                                                       │
                                                      Zabbix Agent already polling → Grafana
```

## 1. Deploy the load generator — [`cpu_load_app.py`](../scripts/cpu_load_app.py)

On each of `ec2-target-01`, `gcp-target-01`, and the on-prem target:
```bash
pip3 install flask --break-system-packages
# paste cpu_load_app.py onto the host (nano + paste is the most reliable method
# across SSH-in-browser / PowerShell / different OSes)
nohup python3 cpu_load_app.py > flask.log 2>&1 &
curl http://127.0.0.1:5000/        # sanity check
```

Open firewall port 5000 **inbound from your JMeter machine's IP** on each cloud (see `02-aws-setup.md` / `03-gcp-setup.md` for the exact Security Group / Firewall Rule). The on-prem host needs no cloud firewall — just check `sudo ufw status`; if active, `sudo ufw allow 5000/tcp`.

## 2. Run the test — [`hybrid_cloud_load_test.jmx`](../load-testing/hybrid_cloud_load_test.jmx)

Requires Java + Apache JMeter (https://jmeter.apache.org/download_jmeter.cgi).

Open the `.jmx` in JMeter, edit the **User Defined Variables** on the Test Plan node:
- `AWS_HOST` / `GCP_HOST` — current **public** IP of each VM (these are dynamic and change on stop/start — re-check before every run)
- `ONPREM_HOST` — the on-prem host's LAN IP (static, usually no need to change)

The plan has 3 Thread Groups (AWS / GCP / On-Prem), each looping GET requests against `/load` on its target. Default: 15 threads, 5s ramp-up, 300s duration — bump `Number of Threads` and `Duration` in the Thread Group GUI if you want a stronger/longer spike.

Run via the GUI **Start** button for a live demo (acceptable for this light a load), or headless for anything heavier:
```
jmeter -n -t hybrid_cloud_load_test.jmx -l results.jtl
```

## 3. Watching it work

Open the `Hybrid_Cloud_Executive_Overview` Grafana dashboard, set the time range to **Last 15 minutes** and refresh to **5s/10s**. Expect to see all three CPU lines move within roughly 1-2 minutes of starting JMeter, and the visible peak forms over about 5-6 minutes — **start JMeter before you start talking about the performance panels**, not when you reach them, so the data has time to arrive.

Expect CPU to *not* reach 100% on any host — that's correct, not a bug:
- Python's GIL limits the Flask dev server to using one core/vCPU fully, so e.g. a 2-vCPU `t3.micro` tops out near 50%, a 4-core on-prem desktop near 25%
- `e2-micro` on GCP is a burstable/shared-core instance and gets throttled after exceeding its baseline, producing a spike-then-drop shape rather than a sustained plateau

## Cleanup after a demo

```bash
# on each VM
pkill -f cpu_load_app.py
```
Remove or tighten the port-5000 firewall rules you opened in step 1.
