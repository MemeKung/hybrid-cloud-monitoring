# 03 — GCP Setup (Zabbix Proxy + Target)

Mirrors `02-aws-setup.md` with GCP-specific differences called out.

## 1. Account & project basics

1. https://cloud.google.com/free → Get started for free
2. Billing → Budgets & alerts → Create budget ($1, alerts 50/90/100%)
3. Enable the **Compute Engine API**
4. IAM & Admin → Service Accounts → create `zabbix-billing-reader` with roles `Billing Account Viewer` + `Compute Viewer` (add `BigQuery Data Viewer` + `BigQuery Job User` too — needed later for the cost layer, see `04-cost-visibility-layer.md`)

### ⚠️ Service Account keys are blocked by default

Recent GCP projects enforce an Org Policy (`iam.disableServiceAccountKeyCreation`) that blocks downloading a JSON key. **Don't fight it.** Instead:
- Attach the service account directly to the VM at creation time (Advanced options → Security → Service account)
- Your code then uses **Application Default Credentials** — no key file needed at all. This is also the credential pattern Google recommends.

### ⚠️ Watch which project you're in

GCP auto-creates a project called **"My First Project"** for every new account. It is very easy to create the Service Account / VPC / VM in that project by accident while believing you're in your intended project (e.g. `capstone-zabbix-gcp`). Check the project switcher at the top of every Console page before creating resources.

If you do end up split across two projects (e.g. compute resources in "My First Project" but a BigQuery dataset in another), you don't need to migrate anything — grant the service account IAM roles on the *other* project directly (cross-project IAM grants are fully supported) instead of recreating resources.

## 2. Networking

- **VPC**: `vpc-zabbix-gcp`, custom subnet mode
- **Subnet**: `subnet-zabbix-proxy`, region **`us-central1`** (or `us-west1`/`us-east1`) — these are the only regions where `e2-micro` is covered by the **Always Free** tier. Any other region bills immediately.
- **Boot disk type matters for Always Free too**: only Standard (HDD) persistent disk, 30 GB, is free. The Console's current default is often "Balanced" (SSD), which is **not** free. Check this on every VM you create.
- **Always Free only covers one `e2-micro` instance per account.** Running a second one (e.g. proxy + target both as `e2-micro`) means the second instance is billed.

Firewall rules (VPC network → Firewall):

| Name | Direction | Target tag | Source | Port |
|---|---|---|---|---|
| `fw-zabbix-gcp-allow` | Ingress | `zabbix-proxy` | on-prem public IP /32 | TCP 10050-10051 |
| `fw-zabbix-gcp-ssh` | Ingress | `zabbix-proxy` | `0.0.0.0/0` | TCP 22 |
| `fw-zabbix-target-allow` | Ingress | `zabbix-target` | proxy's internal IP /32 | TCP 10050 |
| `fw-zabbix-target-ssh` | Ingress | `zabbix-target` | `35.235.240.0/20` | TCP 22 |
| `fw-zabbix-target-jmeter` | Ingress | `zabbix-target` | load-testing machine IP /32 | TCP 5000 |

> `35.235.240.0/20` is Google's fixed IAP range used by the Console's built-in **SSH-in-browser** button. Without this rule, the SSH button fails with *"Connection via Cloud Identity-Aware Proxy Failed"*.

## 3. Launch the Proxy VM

Compute Engine → Create instance:
- Name: `zabbix-proxy-gcp`, Region `us-central1`, machine type `e2-micro`
- Boot disk: Ubuntu 24.04 LTS, **Standard persistent disk**, 30 GB
- Advanced → Security → Service account: `zabbix-billing-reader`, access scope "Allow full access to all Cloud APIs"
- Advanced → Networking: network tag `zabbix-proxy`, network/subnet as above

## 4. Install Zabbix Proxy

Identical package install to AWS (`02-aws-setup.md` §4), with one key difference: **set Passive mode from the start** — there's no reason to repeat AWS's Active→Passive trial and error once you already know the NAT topology requires Passive.

`/etc/zabbix/zabbix_proxy.conf`:
```ini
Server=<on-prem public IP>
Hostname=zabbix-proxy-gcp
ProxyMode=1
DBName=/var/lib/zabbix/zabbix_proxy.db

TLSAccept=psk
TLSConnect=psk
TLSPSKIdentity=PSK-GCP-Proxy
TLSPSKFile=/etc/zabbix/enc/proxy_psk.txt
```

Register in the Web UI the same way as the AWS proxy (Passive mode, PSK identity `PSK-GCP-Proxy`).

## 5. Target VM + Auto-Discovery

Same pattern as AWS — see `02-aws-setup.md` §6-7. Use:
- `gcp-target-01`, network tag `zabbix-target`
- Agent config `Server=`/`ServerActive=` pointing at the proxy's **internal** IP
- Discovery rule IP range matching the GCP subnet (e.g. `10.1.1.1-254`), proxy = `zabbix-proxy-gcp`

## Known issues & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `Service account key creation is disabled` | Org Policy blocks key downloads | Attach the service account to the VM instead; use Application Default Credentials |
| SSH-in-browser: *Connection via Cloud Identity-Aware Proxy Failed* | No firewall rule for the IAP range on port 22 | Add `fw-zabbix-target-ssh` above |
| `zabbix_get`/`curl` to the target times out even though everything "looks" configured right | Usually a Firewall rule targeting the wrong tag, or VM missing the network tag entirely | Re-check Target tags on both the VM and the firewall rule match exactly |
| 403/Permission denied calling BigQuery or Compute APIs from a script running on the proxy | Service account created in a different project than the resource, or missing role | Grant the role on the correct project directly (cross-project IAM grant), don't recreate resources |
