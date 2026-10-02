# Zabbix Configuration Reference — สรุป Config ไฟล์ทั้งหมดในโปรเจค

รวบรวม Config จริงที่ตั้งค่าไว้บนทุกเครื่องในระบบ Hybrid Cloud Infrastructure Monitoring Dashboard
(ใช้สำหรับใส่สไลด์ประกอบ Final Presentation)

---

## 1. Zabbix Server — `172.16.46.104`

### `/etc/zabbix/zabbix_server.conf`
```ini
DBPassword=<password ที่ตั้งไว้ตอนสร้าง MariaDB user 'zabbix'>
```

### `/etc/zabbix/zabbix_agent2.conf` (Agent ของ Server เอง — Monitor ตัวเอง)
```ini
Server=127.0.0.1
ServerActive=127.0.0.1
Hostname=Zabbix server
```

---

## 2. On-Prem Agent — `172.16.46.92`

### `/etc/zabbix/zabbix_agent2.conf`
```ini
Server=172.16.46.104
ServerActive=172.16.46.104
Hostname=Zabbix Agent
```

---

## 3. AWS — Zabbix Proxy (`zabbix-proxy-aws`)

### `/etc/zabbix/zabbix_proxy.conf`
```ini
Server=202.29.180.99
Hostname=zabbix-proxy-aws
ProxyMode=1
DBName=/var/lib/zabbix/zabbix_proxy.db

TLSAccept=psk
TLSConnect=psk
TLSPSKIdentity=PSK-AWS-Proxy
TLSPSKFile=/etc/zabbix/enc/proxy_psk.txt
```
> `ProxyMode=1` = Passive Mode — Server เป็นฝ่ายเชื่อมออกไปหา Proxy (จำเป็นเพราะ Zabbix Server อยู่หลัง Private IP ที่ Internet เข้าไม่ถึง)
> `Server=` ใช้ **Public IP ของเครือข่าย On-Prem** ไม่ใช่ Private IP ของ Zabbix Server เอง

### `/etc/zabbix/zabbix_agent2.conf` (บน `ec2-target-01`)
```ini
Server=10.0.1.10
ServerActive=10.0.1.10
Hostname=ec2-target-01
```
> ใช้ Private IP ของ Proxy เพราะอยู่ใน VPC เดียวกัน ไม่ต้องผ่าน Internet

---

## 4. GCP — Zabbix Proxy (`zabbix-proxy-gcp`)

### `/etc/zabbix/zabbix_proxy.conf`
```ini
Server=202.29.180.99
Hostname=zabbix-proxy-gcp
ProxyMode=1
DBName=/var/lib/zabbix/zabbix_proxy.db

TLSAccept=psk
TLSConnect=psk
TLSPSKIdentity=PSK-GCP-Proxy
TLSPSKFile=/etc/zabbix/enc/proxy_psk.txt
```
> ตั้งเป็น Passive Mode ตั้งแต่แรก (ต่างจาก AWS ที่ต้องสลับทีหลัง) เพราะเรียนรู้จากปัญหาที่เจอตอนตั้ง AWS มาก่อนแล้ว

### `/etc/zabbix/zabbix_agent2.conf` (บน `gcp-target-01`)
```ini
Server=10.1.1.3
ServerActive=10.1.1.3
Hostname=gcp-target-01
```

---

## 5. Zabbix Items/Keys ที่ Custom เพิ่มเอง (Template: `Custom Linux Extended`)

| Item Name | Key | Type |
|---|---|---|
| Zombie process count | `proc.num[,,zomb]` | Zabbix agent |
| Zabbix agent availability | `zabbix[host,agent,available]` | Zabbix internal |

## 6. Cost Visibility Layer — Trapper Items

| Item Name | Key | Host |
|---|---|---|
| AWS Total Daily Cost | `aws.cost.total` | AWS-Cost-Monitor |
| AWS Cost by Service (LLD) | `aws.cost.discovery` → `aws.cost.service[{#SERVICE}]` | AWS-Cost-Monitor |
| GCP Total Daily Cost | `gcp.cost.total` | GCP-Cost-Monitor |
| GCP Cost by Service (LLD) | `gcp.cost.discovery` → `gcp.cost.service[{#SERVICE}]` | GCP-Cost-Monitor |

## 7. Network Summary

| Environment | VPC/Network | Subnet/IP Range |
|---|---|---|
| On-Prem | — | `192.168.10.0/24` (ตามเอกสาร 1.3) / Agent จริงที่ `172.16.46.x` |
| AWS | `vpc-zabbix-aws` | `10.0.1.0/24` (us-east-1) |
| GCP | `vpc-zabbix-gcp` | `10.1.1.0/24` (us-central1) |
