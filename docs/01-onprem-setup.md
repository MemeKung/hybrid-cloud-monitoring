# 01 — On-Premise Zabbix Server & Agent Setup

Reference environment: Ubuntu, Zabbix 7.0.28, MariaDB, Apache2.
Zabbix Server IP used throughout this guide: `172.16.46.104`.

## 1. Install Zabbix Server

```bash
sudo apt update && sudo apt upgrade -y
sudo hostnamectl set-hostname zabbix-server
sudo timedatectl set-timezone Asia/Bangkok

sudo apt install mariadb-server -y
sudo mysql_secure_installation
```

Create the Zabbix database:

```bash
sudo mysql -u root -p
```
```sql
CREATE DATABASE zabbix CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE USER 'zabbix'@'localhost' IDENTIFIED BY 'YOUR_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON zabbix.* TO 'zabbix'@'localhost';
SET GLOBAL log_bin_trust_function_creators = 1;
FLUSH PRIVILEGES;
EXIT;
```

Add the Zabbix repository and install the server + frontend:

```bash
wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo apt update
sudo apt install zabbix-server-mysql zabbix-frontend-php zabbix-apache-conf zabbix-sql-scripts zabbix-agent2 -y
```

> Swap `ubuntu24.04` for `ubuntu22.04` if your server runs 22.04 LTS — check with `lsb_release -a`.

Import the schema:

```bash
zcat /usr/share/zabbix-sql-scripts/mysql/server.sql.gz | mysql -u zabbix -p zabbix
```

Edit `/etc/zabbix/zabbix_server.conf`:
```ini
DBPassword=YOUR_STRONG_PASSWORD
```

Fix the PHP timezone (prevents a red item in the frontend pre-requisite check) in `/etc/zabbix/apache.conf`:
```
php_value date.timezone Asia/Bangkok
```

Start everything:
```bash
sudo systemctl restart zabbix-server zabbix-agent2 apache2 mariadb
sudo systemctl enable zabbix-server zabbix-agent2 apache2 mariadb
```

## 2. Configure the Server's own Agent (self-monitoring)

`/etc/zabbix/zabbix_agent2.conf`:
```ini
Server=127.0.0.1
ServerActive=127.0.0.1
Hostname=Zabbix server
```
```bash
sudo systemctl restart zabbix-agent2
```

## 3. Web UI First-Run

Open `http://<server-ip>/zabbix`, walk the installer wizard, point it at the `zabbix` MySQL user/password, log in as `Admin`/`zabbix`, and **change the password immediately**.

Confirm: **Monitoring → Hosts** should show "Zabbix server" with a green **ZBX** badge.

## 4. On-Prem target agent

On any Ubuntu host you want to monitor (example used throughout this project: `172.16.46.92`):

```bash
sudo apt update && sudo apt install -y wget
wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo apt update
sudo apt install zabbix-agent2 -y
```

`/etc/zabbix/zabbix_agent2.conf`:
```ini
Server=172.16.46.104
ServerActive=172.16.46.104
Hostname=Zabbix Agent
```
```bash
sudo systemctl restart zabbix-agent2
sudo systemctl enable zabbix-agent2
```

Add it in the UI: **Data collection → Hosts → Create host**, host name `Zabbix Agent`, host group e.g. `Linux servers`, Agent interface on its IP, template `Linux by Zabbix agent (active)`.

## 5. Custom Template — `Custom Linux Extended`

This template adds two items that are **not** part of the stock `Linux by Zabbix agent` template, and both are referenced by every Grafana dashboard in this repo.

**Data collection → Templates → Create template**, name `Custom Linux Extended`.

| Item name | Key | Type | Notes |
|---|---|---|---|
| Zombie process count | `proc.num[,,zomb]` | Zabbix agent | Pair with a trigger `last()>10` severity Warning |
| Zabbix agent availability | `zabbix[host,agent,available]` | Zabbix internal | Add value mapping 0=Unknown, 1=Available, 2=Not available |

Link this template to every host you want the "Zombie Processes" / "Agent Availability" dashboard panels to work for (On-Prem, AWS target, GCP target).

## Known issues & fixes

| Symptom | Cause | Fix |
|---|---|---|
| Host shows red `ZBX`, `Connection refused` on port 10050 | Agent on that host not started, or `Hostname=` doesn't match the host name in the Web UI exactly (case-sensitive) | `sudo systemctl restart zabbix-agent2`, double-check `Hostname=` spelling |
| `Permission denied` reading `/var/lib/zabbix` or config files | Normal — those paths are owned by the `zabbix` user | Prefix commands with `sudo` |
