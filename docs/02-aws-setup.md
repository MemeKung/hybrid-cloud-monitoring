# 02 — AWS Setup (Zabbix Proxy + Target)

## 1. Account basics

1. Sign up at https://aws.amazon.com/free
2. Enable MFA on the root user (IAM → Security credentials)
3. Billing → Billing preferences → enable **Receive Free Tier Usage Alerts**
4. Billing → Budgets → **Create a budget** → template **Zero spend budget** (simplest) and/or a custom **Cost budget** at e.g. $1 with alerts at 50/80/100%
5. IAM → Users → Create user `zabbix-admin` with `AdministratorAccess` (or scope it down) → create an Access Key for CLI/SDK use (used later by the cost aggregator script)

## 2. Networking

- **VPC**: `vpc-zabbix-aws`, CIDR `10.0.0.0/16`
- **Subnet**: `subnet-zabbix-proxy`, CIDR `10.0.1.0/24`, in your chosen AZ
- **Internet Gateway**: create and attach to the VPC
- **Route table**: add `0.0.0.0/0 → igw` and associate the subnet

> ⚠️ AWS auto-creates a **Default VPC** in every account — double check the **VPC** column before editing any route table; it's easy to edit the wrong one.

**Security Group** `sg-zabbix-aws` (for the proxy):
| Type | Port | Source |
|---|---|---|
| Custom TCP | 10050-10051 | Your on-prem public IP /32 |
| SSH | 22 | My IP |

**Security Group** `sg-zabbix-target` (for target EC2 instances):
| Type | Port | Source |
|---|---|---|
| Custom TCP | 10050 | Proxy's **private** IP /32 |
| SSH | 22 | My IP |
| TCP | 5000 | Your load-testing machine's IP /32 (only needed for the JMeter demo, see `08-load-testing.md`) |
| TCP | 22 | `35.235.240.0/20` — **only needed on GCP**, not AWS (IAP range) |

## 3. Launch the Proxy instance

EC2 → Launch instance:
- Name: `zabbix-proxy-aws`
- AMI: Ubuntu 24.04 LTS (pick the plain SSD volume type, **not** one bundled with extra software like SQL Server — those aren't Free Tier)
- Instance type: `t2.micro` or `t3.micro`
- Key pair: create and download a new one
- Network: the VPC/subnet above, security group `sg-zabbix-aws`, auto-assign public IP **Enable**
- Storage: 8 GiB default

## 4. Install Zabbix Proxy

```bash
sudo apt update && sudo apt upgrade -y
sudo hostnamectl set-hostname zabbix-proxy-aws
sudo timedatectl set-timezone Asia/Bangkok
sudo apt install sqlite3 curl -y

wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo apt update
sudo apt install zabbix-proxy-sqlite3 zabbix-agent2 zabbix-get zabbix-sender zabbix-sql-scripts -y

sudo mkdir -p /var/lib/zabbix
sudo chown zabbix:zabbix /var/lib/zabbix
sudo chmod 750 /var/lib/zabbix
```

Import the schema — **check the real filename first**, newer Zabbix releases ship it uncompressed:
```bash
ls /usr/share/zabbix-sql-scripts/sqlite3/
# if you see proxy.sql (no .gz):
sudo sqlite3 /var/lib/zabbix/zabbix_proxy.db < /usr/share/zabbix-sql-scripts/sqlite3/proxy.sql
# if you see proxy.sql.gz instead:
# zcat /usr/share/zabbix-sql-scripts/sqlite3/proxy.sql.gz | sudo sqlite3 /var/lib/zabbix/zabbix_proxy.db
sudo chown zabbix:zabbix /var/lib/zabbix/zabbix_proxy.db
```

Create the PSK key:
```bash
sudo mkdir -p /etc/zabbix/enc
sudo sh -c 'openssl rand -hex 32 > /etc/zabbix/enc/proxy_psk.txt'
sudo chown zabbix:zabbix /etc/zabbix/enc/proxy_psk.txt
sudo chmod 600 /etc/zabbix/enc/proxy_psk.txt
sudo cat /etc/zabbix/enc/proxy_psk.txt   # copy this value
```

`/etc/zabbix/zabbix_proxy.conf`:
```ini
Server=<your on-prem PUBLIC IP, e.g. 202.29.180.99>
Hostname=zabbix-proxy-aws
ProxyMode=1
DBName=/var/lib/zabbix/zabbix_proxy.db

TLSAccept=psk
TLSConnect=psk
TLSPSKIdentity=PSK-AWS-Proxy
TLSPSKFile=/etc/zabbix/enc/proxy_psk.txt
```

> **`ProxyMode=1` (Passive) is required**, not optional, whenever the Zabbix Server sits behind a private/NATed IP with no port-forwarding — which is the normal case for a university/home lab. Active mode (`ProxyMode=0`) will time out forever in that topology. See `TROUBLESHOOTING.md` for the full story of why this matters.
> `Server=` must be the on-prem network's **public** IP, not the Zabbix Server's private LAN IP — the proxy is reached over the internet.

```bash
sudo systemctl restart zabbix-proxy
sudo systemctl enable zabbix-proxy
```

## 5. Register the Proxy in the Web UI

**Data collection → Proxies → Create proxy**
- Name: `zabbix-proxy-aws`
- Mode: **Passive**
- Interface: the proxy's **public** IP, port 10051
- Encryption tab → Connections to proxy → PSK → identity `PSK-AWS-Proxy`, paste the PSK value

Confirm: the Proxies list should show the proxy with a recent "Last seen (age)".

## 6. Launch a target EC2 instance and install the Agent

Launch another instance `ec2-target-01`, same VPC/subnet, security group `sg-zabbix-target`.

```bash
wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo apt update
sudo apt install zabbix-agent2 -y
```
`/etc/zabbix/zabbix_agent2.conf`:
```ini
Server=10.0.1.10        # proxy's PRIVATE IP — same VPC, no internet hop needed
ServerActive=10.0.1.10
Hostname=ec2-target-01
```
```bash
sudo systemctl restart zabbix-agent2
```

Add the host in the UI with **Monitored by proxy = zabbix-proxy-aws**, templates `Linux by Zabbix agent` + `Custom Linux Extended`.

## 7. Auto-Discovery (LLD)

**Data collection → Discovery → Create discovery rule**
- Discovery by proxy: `zabbix-proxy-aws`
- IP range: `10.0.1.1-254`
- Checks: `agent.ping` (port 10050) + `agent.hostname`
- **Device uniqueness criteria** and **Host name**: set both to `agent.hostname` — not the default "IP address", otherwise discovered hosts get named after their IP instead of their real hostname.

**Data collection → Actions → Discovery actions → Create action**
- Conditions: Discovery rule = the rule above AND Discovery status = Up
- Operations: Add host → Add to host group → Link templates. Remember to populate **Operations**, not just Conditions — a saved action with conditions but no operations is rejected by Zabbix.
