# Hybrid Cloud Infrastructure Monitoring Dashboard

โครงงานวิศวกรรมคอมพิวเตอร์ ระบบนี้ใช้ Zabbix 7.0 กับ Grafana มอนิเตอร์เครื่องเซิร์ฟเวอร์สามที่ในหน้าเดียว คือเครื่องในห้องแล็บ (on-premise), AWS และ GCP แล้วเอาค่าใช้จ่ายจริงจากบิลของ AWS กับ GCP มาแสดงคู่กับกราฟ CPU และ Memory นอกจากนี้ยังมีแจ้งเตือนเข้า LINE สรุปค่าใช้จ่ายรายวัน และชุดทดสอบโหลดด้วย JMeter

README นี้เขียนเป็นคู่มือให้คนอื่นทำตามได้ เรียงตามลำดับที่ควรทำ ซึ่งใกล้เคียงกับที่เราทำจริง (ตอนทำจริงเราทำ AWS ก่อน GCP และทำ Grafana ก่อนแจ้งเตือน LINE) ทุกบั๊กและทางตันที่เราเจอระหว่างทางจดไว้ในหัวข้อ "ปัญหาที่เจอและวิธีแก้" ท้ายเอกสาร ถ้าติดตรงไหนให้ไปดูตรงนั้นก่อน

ข้อตกลงในเอกสารนี้

- ค่าที่อยู่ในเครื่องหมาย `< >` เช่น `<ON_PREM_PUBLIC_IP>` ต้องแทนด้วยค่าของตัวเอง
- IP `172.16.46.104` (Zabbix Server) กับ `172.16.46.92` (เครื่อง on-prem ที่ถูกมอนิเตอร์) เป็นของแล็บเรา แทนด้วย IP ของตัวเองได้เลย
- ใน repo นี้ไม่มี token, PSK หรือ password จริงอยู่ ทุกที่ที่ต้องใส่ความลับจะเป็น `PASTE_..._HERE` หรือ `<...>`
- คำสั่งที่ขึ้นต้นด้วยชื่อเครื่อง เช่น "บน zabbix-proxy-aws" หมายถึงต้องพิมพ์ในเครื่องนั้นผ่าน SSH

## สารบัญ

1. ภาพรวมและค่าที่ใช้ในโปรเจกต์
2. สิ่งที่ต้องเตรียม
3. Zabbix Server บนเครื่อง on-premise
4. Agent บนเครื่อง on-premise และ Template เสริม
5. AWS: ตั้ง VPC, Proxy, เครื่องเป้าหมาย และ Auto-Discovery
6. GCP: ตั้ง VPC, Proxy และเครื่องเป้าหมาย
7. ดึงค่าใช้จ่ายจาก AWS และ GCP เข้า Zabbix
8. Grafana
9. แจ้งเตือนเข้า LINE
10. สรุปค่าใช้จ่ายรายวันเข้า LINE
11. ทดสอบโหลดด้วย JMeter
12. การทดลองเรื่องค่าใช้จ่าย (Cloud Cost Experiment)
13. ปัญหาที่เจอและวิธีแก้
14. เรื่องความลับและการปิดเครื่องหลังใช้งาน
15. ไฟล์ใน repo นี้

---

## 1. ภาพรวมและค่าที่ใช้ในโปรเจกต์

Zabbix Server ติดตั้งอยู่ที่เดียว คือบนเครื่อง on-premise เครื่องที่อยู่ใน AWS กับ GCP ไม่คุยกับ server ตรงๆ แต่ผ่าน Zabbix Proxy ที่ตั้งไว้ฝั่งละตัว แล้ว proxy ค่อยส่งข้อมูลกลับมาที่ server ส่วนเครื่อง on-prem คุยกับ server ตรงๆ ตามปกติ

Proxy ทั้งสองตัวตั้งเป็น Passive mode และเข้ารหัสด้วย PSK เหตุผลคือ Zabbix Server อยู่หลัง NAT ของเครือข่ายแล็บ ไม่มีใครบนอินเทอร์เน็ตเชื่อมเข้ามาที่ server ได้ ถ้าตั้ง proxy เป็น Active (proxy ต่อเข้าหา server เอง) จะไม่มีทางต่อติด ต้องกลับด้านให้ server เป็นฝ่ายต่อออกไปหา proxy แทน เรื่องนี้เราเสียเวลาไปนานตอนทำ AWS รายละเอียดอยู่ในส่วนที่ 5 และในหัวข้อปัญหา

ค่าใช้จ่ายของ cloud ดึงด้วยสคริปต์ Python สองตัวที่รันบน proxy ของแต่ละฝั่ง วันละครั้ง สคริปต์ส่งผลเข้า Zabbix ผ่าน `zabbix_sender` เป็น trapper item และใช้ Low-Level Discovery (LLD) เพื่อให้บริการ cloud ตัวใหม่ๆ มี item ของตัวเองขึ้นมาเองโดยไม่ต้องสร้างด้วยมือ Grafana ติดตั้งในเครื่องเดียวกับ Zabbix Server และอ่านข้อมูลผ่าน Zabbix API

ค่าที่ใช้ในโปรเจกต์

| ชื่อ | อยู่ที่ | ค่า |
|---|---|---|
| Zabbix Server | on-prem | 172.16.46.104, Ubuntu 22.04, Zabbix 7.0.28, MariaDB, Apache, Grafana (port 3000) |
| Zabbix Agent (ชื่อ host ใน Zabbix คือ `Zabbix Agent`) | on-prem | 172.16.46.92, Ubuntu 22.04 |
| zabbix-proxy-aws | AWS us-east-1 | VPC `vpc-zabbix-aws` 10.0.0.0/16, subnet `subnet-zabbix-proxy` 10.0.1.0/24 |
| ec2-target-01 | AWS | อยู่ใน subnet เดียวกับ proxy |
| zabbix-proxy-gcp | GCP us-central1 | VPC `vpc-zabbix-gcp`, subnet 10.1.1.0/24, IP ภายใน 10.1.1.3 |
| gcp-target-01 | GCP | 10.1.1.4 |

ชื่อ host ใน Zabbix ต้องตั้งให้ตรงตามตารางนี้ (`ec2-target-01`, `gcp-target-01`, `Zabbix Agent`, `AWS-Cost-Monitor`, `GCP-Cost-Monitor`) เพราะ dashboard ของ Grafana ที่แนบมาค้นหา host ด้วยชื่อเหล่านี้

---

## 2. สิ่งที่ต้องเตรียม

- เครื่อง Ubuntu 22.04 หรือ 24.04 หนึ่งเครื่องสำหรับ Zabbix Server ต้องออกอินเทอร์เน็ตได้ และเปิดให้เราเข้าถึง port 80 กับ 3000 จากเครื่องที่เราใช้งานอยู่ได้
- เครื่อง Linux อีกหนึ่งเครื่องใน LAN เดียวกันสำหรับเป็น target ฝั่ง on-prem
- บัญชี AWS และบัญชี GCP ทั้งสองมี free tier พอสำหรับโปรเจกต์นี้ แต่ต้องตั้ง Budget Alert ก่อนสร้างอะไรทั้งสิ้น (อยู่ในส่วนที่ 5 และ 6)
- บัญชี LINE สำหรับสร้าง LINE Official Account
- เครื่องที่ใช้ยิง JMeter (ติดตั้ง Java และ Apache JMeter)
- Python 3 บนทุกเครื่องที่ต้องรันสคริปต์

สิ่งสำคัญที่ต้องรู้ก่อนเริ่มคือ Public IP ของเครือข่ายที่ Zabbix Server อยู่ เพราะต้องเอาไปใส่ใน config ของ proxy และในกฎ firewall ของทั้งสอง cloud เช็คได้จากเครื่อง Zabbix Server

```bash
curl -s ifconfig.me; echo
```

ค่านี้ในที่นี้เรียกว่า `<ON_PREM_PUBLIC_IP>` ถ้าเครือข่ายของคุณเป็นแบบ IP เปลี่ยนได้ (บ้านหรือมหาวิทยาลัยส่วนใหญ่เป็นแบบนี้) วันที่ IP เปลี่ยนระบบฝั่ง cloud จะขาดการติดต่อ ต้องกลับมาแก้ 3 ที่ คือ `Server=` ใน config ของ proxy ทั้งสองตัว, Security Group ของ AWS และ Firewall rule ของ GCP

ค่าใช้จ่ายที่ต้องระวัง ทุกอย่างในโปรเจกต์นี้ออกแบบให้อยู่ใน free tier แต่มีจุดที่หลุดได้ง่าย

- AWS: EC2 ที่เปิดทิ้งไว้เกินโควตา public IPv4 address, EBS volume ที่ลืมลบ และการเรียก Cost Explorer API (คิดครั้งละประมาณ 0.01 USD สคริปต์เราเรียกวันละครั้ง)
- GCP: Always Free ให้ `e2-micro` แค่ 1 เครื่องต่อบัญชี เครื่องที่สองคิดเงินตามชั่วโมง, ให้เฉพาะ region us-central1, us-west1, us-east1 และให้เฉพาะดิสก์ Standard (HDD) ถ้า Console ตั้งค่าเริ่มต้นเป็น Balanced ต้องเปลี่ยนเอง
- ทั้งสอง cloud: เครื่องที่ไม่ได้ใช้ให้ Stop ไว้ ดูหัวข้อสุดท้ายของเอกสาร

---

## 3. Zabbix Server บนเครื่อง on-premise

ทำบนเครื่อง `172.16.46.104` (Ubuntu 22.04) ถ้าเครื่องของคุณเป็นเวอร์ชันอื่นให้ดูด้วย `lsb_release -a` แล้วแก้ชื่อไฟล์ใน URL ของ repo ให้ตรง (เช่น `ubuntu24.04`)

### 3.1 เตรียมเครื่องและฐานข้อมูล

```bash
sudo apt update && sudo apt upgrade -y
sudo hostnamectl set-hostname zabbix-server
sudo timedatectl set-timezone Asia/Bangkok

sudo apt install mariadb-server -y
sudo mysql_secure_installation
```

สร้างฐานข้อมูลของ Zabbix

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

### 3.2 ติดตั้ง Zabbix Server และ Frontend

```bash
wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu22.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu22.04_all.deb
sudo apt update
sudo apt install zabbix-server-mysql zabbix-frontend-php zabbix-apache-conf zabbix-sql-scripts zabbix-agent2 -y
```

นำเข้า schema (จะถามรหัสผ่านของ user `zabbix`) แล้วปิด option ที่เปิดไว้ตอนสร้างฐานข้อมูล

```bash
zcat /usr/share/zabbix-sql-scripts/mysql/server.sql.gz | mysql --default-character-set=utf8mb4 -uzabbix -p zabbix
sudo mysql -u root -p -e "SET GLOBAL log_bin_trust_function_creators = 0;"
```

ใส่รหัสผ่านฐานข้อมูลใน `/etc/zabbix/zabbix_server.conf`

```ini
DBPassword=YOUR_STRONG_PASSWORD
```

เปิดบริการ

```bash
sudo systemctl restart zabbix-server zabbix-agent2 apache2 mariadb
sudo systemctl enable zabbix-server zabbix-agent2 apache2 mariadb
```

### 3.3 Agent ของ Server เอง

ไฟล์ `/etc/zabbix/zabbix_agent2.conf` บน Zabbix Server

```ini
Server=127.0.0.1
ServerActive=127.0.0.1
Hostname=Zabbix server
```

```bash
sudo systemctl restart zabbix-agent2
```

### 3.4 ตั้งค่าผ่านหน้าเว็บครั้งแรก

1. เปิด `http://172.16.46.104/zabbix` ในเบราว์เซอร์ จะเจอ installer wizard
2. หน้า Prerequisites ควรผ่านทั้งหมด ถ้าติดเรื่อง PHP timezone ให้เปิดไฟล์ `/etc/zabbix/apache.conf` แก้บรรทัด `php_value date.timezone` เป็น `Asia/Bangkok` แล้ว `sudo systemctl restart apache2`
3. หน้า Database ใส่ host `localhost`, ชื่อฐานข้อมูล `zabbix`, user `zabbix` และรหัสผ่านที่ตั้งไว้
4. หน้า Settings ตั้ง Default time zone เป็น `(UTC+7:00) Asia/Bangkok`
5. ล็อกอินด้วย `Admin` / `zabbix` แล้วเปลี่ยนรหัสผ่านทันที ที่ Users, Users, คลิก Admin, ปุ่ม Change password

ตรวจว่าใช้ได้: ไปที่ Monitoring, Hosts จะเห็น host `Zabbix server` และป้าย ZBX สีเขียว (รอสักหนึ่งถึงสองนาที)

---

## 4. Agent บนเครื่อง on-premise และ Template เสริม

### 4.1 ติดตั้ง Agent 2 บนเครื่อง 172.16.46.92

```bash
wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu22.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu22.04_all.deb
sudo apt update
sudo apt install zabbix-agent2 -y
```

แก้ `/etc/zabbix/zabbix_agent2.conf`

```ini
Server=172.16.46.104
ServerActive=172.16.46.104
Hostname=Zabbix Agent
```

```bash
sudo systemctl restart zabbix-agent2
sudo systemctl enable zabbix-agent2
```

ค่า `Hostname=` ต้องตรงกับชื่อ host ที่จะสร้างในหน้าเว็บทุกตัวอักษร (ตัวพิมพ์เล็กใหญ่มีผล) ถ้าไม่ตรง ZBX จะไม่เขียวและ active check จะไม่ทำงาน

### 4.2 สร้าง Host Group

ที่หน้าเว็บ Zabbix ไปที่ Data collection, Host groups, Create host group สร้างสี่กลุ่มนี้ไว้ก่อน เพราะส่วนถัดๆ ไปจะอ้างถึง

- `Linux servers` (มีอยู่แล้วโดย default)
- `AWS EC2`
- `GCP Compute Engine`
- `Cost Monitoring`

### 4.3 เพิ่ม host

Data collection, Hosts, Create host

- Host name: `Zabbix Agent`
- Templates: `Linux by Zabbix agent`
- Host groups: `Linux servers`
- Interfaces: Add, Agent, IP address `172.16.46.92`, port `10050`
- Monitored by: Server

กด Add แล้วรอ 1 ถึง 2 นาที ป้าย ZBX ต้องเป็นสีเขียว (ถ้าเป็นแดงดูหัวข้อ "ZBX แดง" ในส่วนที่ 13)

### 4.4 สร้าง Template เสริม Custom Linux Extended

Template `Linux by Zabbix agent` ของ Zabbix ไม่มี item นับ zombie process เราเลยทำ template เพิ่มอีกอัน dashboard ทุกไฟล์ใน repo นี้ใช้ item สองตัวจากมัน

Data collection, Templates, Create template

- Template name: `Custom Linux Extended`
- Template groups: เลือกกลุ่มที่มีอยู่แล้ว เช่น `Templates/Operating systems`

บันทึกแล้วเปิด template ที่สร้าง ไปแท็บ Items, Create item สองรายการ

| Name | Type | Key | Type of information |
|---|---|---|---|
| `Zombie process count` | Zabbix agent | `proc.num[,,zomb]` | Numeric (unsigned) |
| `Zabbix agent availability` | Zabbix internal | `zabbix[host,agent,available]` | Numeric (unsigned) |

ชื่อ item ต้องพิมพ์ตามนี้ เพราะ dashboard ค้นหาด้วยชื่อ

ที่แท็บ Triggers สร้าง trigger หนึ่งอัน ชื่อ `Too many zombie processes on {HOST.NAME}` expression `last(/Custom Linux Extended/proc.num[,,zomb])>10` ความรุนแรง Warning

หลังจากนี้ ทุก host ที่เพิ่มเข้าระบบ (on-prem, AWS, GCP) ให้ผูก template สองตัวคู่กัน คือ `Linux by Zabbix agent` และ `Custom Linux Extended` ให้ host `Zabbix Agent` ที่สร้างไปแล้ว ไปที่ host นั้น แท็บ Templates เพิ่ม `Custom Linux Extended` แล้วกด Update

หมายเหตุเรื่อง item `Zabbix agent availability`: panel "Agent Availability" ใน Grafana ของเราแปลค่า 0 เป็น Unknown, 1 เป็น Available, 2 เป็น Not available ก่อนใช้งานจริงให้ลองหยุด agent (`sudo systemctl stop zabbix-agent2`) แล้วดูค่าที่ item ส่งออกมาใน Monitoring, Latest data ว่าตรงกับการแปลนี้ไหม ถ้าไม่ตรงให้แก้ Value mapping ใน panel (เรายังไม่ได้ยืนยันกับเอกสารของ Zabbix ว่าความหมายของ 0 กับ 2 ตรงกับที่เราตั้ง)

---

## 5. AWS: VPC, Proxy, เครื่องเป้าหมาย และ Auto-Discovery

### 5.1 บัญชีและความปลอดภัยเบื้องต้น

1. สมัครที่ https://aws.amazon.com/free
2. ล็อกอินด้วย root แล้วเปิด MFA ที่ IAM, Security credentials
3. ที่มุมขวาบนเลือก region `US East (N. Virginia) us-east-1` และใช้ region นี้ตลอด
4. Billing and Cost Management, Billing preferences, ติ๊ก Receive Free Tier Usage Alerts และใส่อีเมล
5. Billing and Cost Management, Budgets, Create budget เลือก template `Zero spend budget` หรือสร้าง Cost budget เองที่ 1 USD แล้วตั้งแจ้งเตือนที่ 50%, 80%, 100%

อย่าข้ามข้อ 4 และ 5 ตัวเลขใน Cost Explorer ช้ากว่าความจริงประมาณ 24 ชั่วโมง ถ้าเผลอเปิดอะไรทิ้งไว้ Budget Alert คือสิ่งเดียวที่จะเตือนเรา

### 5.2 สร้าง Network

ไปที่ VPC console (ยังเป็น us-east-1)

1. Your VPCs, Create VPC เลือก "VPC only" ตั้ง Name tag `vpc-zabbix-aws`, IPv4 CIDR `10.0.0.0/16`, Create
2. Subnets, Create subnet เลือก VPC `vpc-zabbix-aws` ตั้งชื่อ `subnet-zabbix-proxy`, เลือก Availability Zone ใดก็ได้, IPv4 CIDR `10.0.1.0/24`, Create
3. Internet gateways, Create internet gateway ชื่อ `igw-zabbix-aws` แล้ว Actions, Attach to VPC เลือก `vpc-zabbix-aws`
4. Route tables เลือก route table ที่คอลัมน์ VPC เป็น `vpc-zabbix-aws` แล้วเข้าแท็บ Routes, Edit routes, Add route: Destination `0.0.0.0/0`, Target เลือก Internet Gateway ที่สร้างไว้ แล้ว Save
5. แท็บ Subnet associations ของ route table เดียวกัน Edit subnet associations ติ๊ก `subnet-zabbix-proxy`

ข้อควรระวังตรงข้อ 4: AWS สร้าง Default VPC ให้ทุกบัญชีอยู่แล้ว และมี route table ของมันอยู่ในรายการเดียวกัน เราเคยแก้ route table ของ Default VPC ผิดตัวมาแล้ว ให้ดูคอลัมน์ VPC ทุกครั้งก่อนกด Edit

### 5.3 Security Group

EC2 console, Security Groups, Create security group สองอัน ทั้งสองเลือก VPC `vpc-zabbix-aws`

`sg-zabbix-aws` (ใช้กับ proxy)

| ประเภท | Port | Source |
|---|---|---|
| Custom TCP | 10050-10051 | `<ON_PREM_PUBLIC_IP>/32` |
| SSH | 22 | My IP |
| Custom TCP (ใส่เฉพาะถ้า agent ใช้ active check) | 10051 | 10.0.1.0/24 |

`sg-zabbix-target` (ใช้กับเครื่องเป้าหมาย)

| ประเภท | Port | Source |
|---|---|---|
| Custom TCP | 10050 | IP ภายใน (private) ของ proxy /32 ซึ่งจะรู้ตอนทำข้อ 5.4 แล้วกลับมาเติม |
| SSH | 22 | My IP |
| Custom TCP | 5000 | IP ของเครื่องที่รัน JMeter /32 (ใส่ตอนทำส่วนที่ 11 เท่านั้น) |

กฎ "My IP" ของ SSH จะใช้ไม่ได้ทันทีที่ IP ของเราเปลี่ยน ถ้า SSH ค้างไปเฉยๆ ให้เข้ามาแก้ source ให้เป็น IP ปัจจุบัน

### 5.4 สร้าง EC2 สำหรับ Proxy

EC2, Launch instance

- Name: `zabbix-proxy-aws`
- AMI: Ubuntu Server 24.04 LTS (เลือกตัวที่มีป้าย Free tier eligible และอย่าเลือก AMI ที่รวม software อย่าง SQL Server มาด้วย เพราะไม่อยู่ใน free tier ตอนเราลอง Ubuntu 22.04 ไม่ขึ้นป้าย free tier เลยเปลี่ยนมา 24.04)
- Instance type: ตัวที่ติดป้าย Free tier eligible (ของเราเป็น `t3.micro`)
- Key pair: Create new key pair, ดาวน์โหลดไฟล์ `.pem` เก็บไว้ให้ดี
- Network settings: Edit แล้วเลือก VPC `vpc-zabbix-aws`, Subnet `subnet-zabbix-proxy`, Auto-assign public IP เป็น Enable, Security group ที่มีอยู่แล้วเลือก `sg-zabbix-aws`
- Storage: 8 GiB ตามค่าเริ่มต้น

ข้อสังเกต: พอเราเปลี่ยน AMI ฟอร์มจะรีเซ็ตบางช่อง (instance type, key pair, security group) ให้เลื่อนตรวจทุกช่องอีกรอบก่อนกด Launch

พอ instance ขึ้นสถานะ Running ให้จดสองค่า

- Public IPv4 address ของ proxy (เรียกว่า `<AWS_PROXY_PUBLIC_IP>`)
- Private IPv4 address ของ proxy (เรียกว่า `<AWS_PROXY_PRIVATE_IP>`)

Public IP จะเปลี่ยนทุกครั้งที่ Stop แล้ว Start instance ถ้าต้องการให้คงที่ต้องใช้ Elastic IP (ซึ่งคิดเงินถ้าไม่ได้ผูกกับ instance ที่กำลังรัน) หรือไม่ก็ยอมแก้ค่าใน Web UI ทุกครั้งที่เปิดเครื่อง

SSH เข้าเครื่อง

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<AWS_PROXY_PUBLIC_IP>
```

ยืนยัน private IP ของเครื่องด้วยคำสั่งนี้ทุกครั้ง อย่าเดาเอาจากชื่อใน console

```bash
hostname -I
```

ตอนทำโปรเจกต์ เราเข้าใจว่า private IP ของ proxy คือ 10.0.1.10 แต่ prompt ของเครื่องแสดง `ip-10-0-1-104` ซึ่งบอกว่าจริงๆ น่าจะเป็น 10.0.1.104 ค่านี้ต้องถูกในทั้ง Security Group ของ target และ `Server=` ในไฟล์ agent ถ้าใส่ผิด `zabbix_get` จาก proxy ไปหา target จะ timeout

กลับไปแก้ `sg-zabbix-target` ใส่ `<AWS_PROXY_PRIVATE_IP>/32` ใน rule port 10050

### 5.5 ติดตั้ง Zabbix Proxy

บน zabbix-proxy-aws

```bash
sudo apt update && sudo apt upgrade -y
sudo hostnamectl set-hostname zabbix-proxy-aws
sudo timedatectl set-timezone Asia/Bangkok
sudo apt install sqlite3 curl -y

wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo apt update
sudo apt install zabbix-proxy-sqlite3 zabbix-agent2 zabbix-get zabbix-sender zabbix-sql-scripts -y
```

ต้องติดตั้ง `zabbix-get` กับ `zabbix-sender` จาก repo ของ Zabbix 7.0 ตัวนี้ ถ้าสั่ง `apt install zabbix-get` ก่อนเพิ่ม repo Ubuntu จะเสนอเวอร์ชัน 6.0 ซึ่งใช้ไม่ได้ดี

สร้างโฟลเดอร์เก็บฐานข้อมูล แล้วนำเข้า schema

```bash
sudo mkdir -p /var/lib/zabbix
sudo chown zabbix:zabbix /var/lib/zabbix
sudo chmod 750 /var/lib/zabbix

ls /usr/share/zabbix-sql-scripts/sqlite3/
sudo sqlite3 /var/lib/zabbix/zabbix_proxy.db < /usr/share/zabbix-sql-scripts/sqlite3/proxy.sql
sudo chown zabbix:zabbix /var/lib/zabbix/zabbix_proxy.db
```

ใน Zabbix 7.0.28 ไฟล์ชื่อ `proxy.sql` (ไม่บีบอัด) ถ้า `ls` เห็น `proxy.sql.gz` แทน ให้ใช้ `zcat ... | sudo sqlite3 ...` ส่วนโฟลเดอร์ `/var/lib/zabbix` ต้องสร้างเองก่อน ไม่งั้น proxy จะฟ้อง "unable to open database file"

สร้าง PSK

```bash
sudo mkdir -p /etc/zabbix/enc
sudo sh -c 'openssl rand -hex 32 > /etc/zabbix/enc/proxy_psk.txt'
sudo chown zabbix:zabbix /etc/zabbix/enc/proxy_psk.txt
sudo chmod 600 /etc/zabbix/enc/proxy_psk.txt
sudo cat /etc/zabbix/enc/proxy_psk.txt
```

ค่าที่พิมพ์ออกมา (ตัวอักษร 64 ตัว) ให้ copy ไปเก็บ จะต้องวางในหน้าเว็บของ Zabbix ในขั้นตอนถัดไป อย่าเอาค่านี้ไปวางในแชทหรือ commit ลง Git เพราะ `ls` หรือ `cat` ไฟล์ในโฟลเดอร์นี้โดยไม่ใช้ `sudo` จะได้ Permission denied เป็นเรื่องปกติ เจ้าของไฟล์คือ user `zabbix`

แก้ `/etc/zabbix/zabbix_proxy.conf` (ใช้ `sudo nano`) ให้บรรทัดเหล่านี้มีค่าตามนี้

```ini
Server=<ON_PREM_PUBLIC_IP>
Hostname=zabbix-proxy-aws
ProxyMode=1
DBName=/var/lib/zabbix/zabbix_proxy.db

TLSAccept=psk
TLSConnect=psk
TLSPSKIdentity=PSK-AWS-Proxy
TLSPSKFile=/etc/zabbix/enc/proxy_psk.txt
```

สองบรรทัดที่ทำให้เราเสียเวลามากที่สุด

- `ProxyMode=1` คือ Passive ถ้าเป็น 0 (Active) proxy จะพยายามต่อเข้า `172.16.46.104:10051` ซึ่งเป็น IP ภายในแล็บ จาก AWS ไปไม่ถึง log จะเงียบหรือ timeout ไม่มีวันขึ้นเขียว
- `Server=` ใน Passive mode คือรายชื่อ IP ที่ proxy ยอมให้เชื่อมเข้ามา connection จาก Zabbix Server ในแล็บจะออกอินเทอร์เน็ตด้วย Public IP ของเครือข่าย (ผ่าน NAT) proxy จึงเห็นต้นทางเป็น `<ON_PREM_PUBLIC_IP>` ไม่ใช่ 172.16.46.104 ถ้าใส่ IP ภายใน log จะขึ้น "connection from ... rejected, allowed hosts: 172.16.46.104"

เริ่ม proxy

```bash
sudo systemctl restart zabbix-proxy
sudo systemctl enable zabbix-proxy
sudo tail -n 30 /var/log/zabbix/zabbix_proxy.log
```

### 5.6 ลงทะเบียน Proxy ในหน้าเว็บ

Administration, Proxies, Create proxy

- Proxy name: `zabbix-proxy-aws` (ต้องตรงกับ `Hostname=` ใน conf)
- Proxy mode: Passive
- Interface: Address `<AWS_PROXY_PUBLIC_IP>`, Port `10051`
- แท็บ Encryption: Connections to proxy เลือก PSK, PSK identity `PSK-AWS-Proxy`, PSK วางค่า 64 ตัวอักษรที่ copy ไว้

กด Add แล้วดูคอลัมน์ Last seen (age) ใน 1 นาที ต้องเปลี่ยนจาก Never เป็นตัวเลขวินาที

ถ้าไม่ขึ้น ให้ทดสอบจาก Zabbix Server ว่าต่อ port ได้ไหม

```bash
nc -vz <AWS_PROXY_PUBLIC_IP> 10051
```

ถ้า timeout ให้กลับไปดู Security Group `sg-zabbix-aws` ว่า source เป็น Public IP ปัจจุบันของแล็บ และ port 10050-10051 ถูกต้อง ถ้าต่อติดแต่ proxy ยังเป็นสีแดง ให้อ่าน `/var/log/zabbix/zabbix_proxy.log` บน proxy

### 5.7 สร้างเครื่องเป้าหมาย ec2-target-01

Launch instance อีกตัว ชื่อ `ec2-target-01` ใช้ AMI และ key pair เดียวกัน เลือก VPC `vpc-zabbix-aws`, subnet `subnet-zabbix-proxy`, Security group `sg-zabbix-target`, Auto-assign public IP เป็น Enable (ต้องมี เพราะเครื่องต้องออกอินเทอร์เน็ตไปโหลดแพ็กเกจ และให้ JMeter ยิงเข้ามาได้ภายหลัง)

SSH เข้าเครื่องใหม่ แล้วติดตั้ง Agent

```bash
wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo apt update
sudo apt install zabbix-agent2 -y
```

แก้ `/etc/zabbix/zabbix_agent2.conf`

```ini
Server=<AWS_PROXY_PRIVATE_IP>
ServerActive=<AWS_PROXY_PRIVATE_IP>
Hostname=ec2-target-01
```

ใช้ IP ภายในของ proxy เพราะอยู่ใน VPC เดียวกัน ไม่ต้องออกอินเทอร์เน็ต

```bash
sudo systemctl restart zabbix-agent2
sudo systemctl enable zabbix-agent2
```

ทดสอบจาก proxy ว่าถามค่า agent ได้ (แทน IP ด้วย private IP ของ target จาก `hostname -I` บนเครื่องนั้น)

```bash
zabbix_get -s <EC2_TARGET_PRIVATE_IP> -p 10050 -k agent.ping
```

ต้องได้ `1` ถ้า timeout แปลว่า Security Group ของ target ยังไม่เปิด 10050 ให้ IP ของ proxy หรือใส่ IP ของ proxy ผิด

ที่หน้าเว็บ Zabbix Data collection, Hosts, Create host

- Host name: `ec2-target-01`
- Templates: `Linux by Zabbix agent` และ `Custom Linux Extended`
- Host groups: `AWS EC2`
- Interfaces: Agent, IP `<EC2_TARGET_PRIVATE_IP>`, port 10050
- Monitored by: Proxy, เลือก `zabbix-proxy-aws`

รอ 1 ถึง 2 นาที ZBX ต้องเขียว

### 5.8 Auto-Discovery

เป้าหมายคือเปิด EC2 เครื่องใหม่ใน subnet นี้แล้วให้ Zabbix เห็นและเพิ่มเข้าระบบเอง โดยเราไม่ต้องไปสร้าง host ด้วยมือ

Data collection, Discovery, Create discovery rule

- Name: `AWS EC2 Auto-Discovery`
- Discovery by: Proxy, เลือก `zabbix-proxy-aws` (สำคัญ เพราะ server ในแล็บไม่เห็น 10.0.1.0/24)
- IP range: `10.0.1.1-254`
- Update interval: `1m` ระหว่างทดสอบ (ค่าเริ่มต้นนานกว่านี้มาก)
- Checks: เพิ่มสองอัน อันแรก Zabbix agent, Key `agent.ping`, Port 10050 อันที่สอง Zabbix agent, Key `agent.hostname`, Port 10050
- Device uniqueness criteria: เลือก `Zabbix agent "agent.hostname"`
- Host name: เลือก `Zabbix agent "agent.hostname"`

ถ้าสองช่องท้ายปล่อยเป็นค่าเริ่มต้น (IP address) host ที่ถูกเพิ่มจะชื่อเป็นตัวเลข IP เช่น `10.0.1.16` แทนที่จะเป็นชื่อเครื่องจริง ตอนทำเราเจอแบบนี้มาแล้ว

จากนั้น Alerts, Actions, Discovery actions, Create action

- Name: `Auto-add AWS EC2 hosts`
- Conditions: Discovery rule เท่ากับ `AWS EC2 Auto-Discovery` และ Discovery status เท่ากับ Up
- Operations: เพิ่มสามรายการ คือ Add host, Add to host groups (`AWS EC2`), Link to templates (`Linux by Zabbix agent` และ `Custom Linux Extended`)

action ที่มีแต่ Conditions โดยไม่ใส่ Operations บันทึกไม่ได้ จะขึ้น "No operations defined"

ทดสอบ: สร้าง EC2 เครื่องที่สองชื่อ `ec2-target-02` ใน subnet และ Security Group เดียวกับ target แรก ติดตั้ง agent เหมือนข้อ 5.7 แต่ตั้ง `Hostname=ec2-target-02` รอไม่เกินสองสามนาที ที่ Monitoring, Discovery จะเห็นอุปกรณ์ขึ้นมา และที่ Data collection, Hosts จะมี `ec2-target-02` เพิ่มเข้ามาเองพร้อม template ครบ (ของเรา IP คือ 10.0.1.16)

ข้อควรรู้: ถ้าลบ host ที่ discovery เพิ่มไปแล้ว แล้วรอให้มันกลับมาใหม่ จะไม่กลับ เพราะ Zabbix สร้างเหตุการณ์เพิ่ม host ตอนที่เพิ่งพบอุปกรณ์เป็นครั้งแรกหรือกลับมาจากสถานะ Down เท่านั้น อุปกรณ์ที่ยังตอบอยู่ตลอดจะไม่ถูกเพิ่มซ้ำ วิธีที่ได้ผลคือหยุด agent บนเครื่องนั้น (`sudo systemctl stop zabbix-agent2`) รอให้หน้า Monitoring, Discovery แสดงว่า Down แล้วสั่ง start ใหม่

---

## 6. GCP: VPC, Proxy และเครื่องเป้าหมาย

โครงเหมือน AWS ทุกอย่าง ต่างกันที่ชื่อเรียกและกฎของ free tier

### 6.1 บัญชีและโปรเจกต์

1. สมัครที่ https://cloud.google.com/free
2. Billing, Budgets & alerts, Create budget ตั้ง 1 USD และแจ้งเตือนที่ 50%, 90%, 100%
3. สร้างโปรเจกต์ใหม่ (ตั้งชื่ออะไรก็ได้ เช่น `my-zabbix-capstone`) แล้วสลับไปทำงานในโปรเจกต์นี้
4. APIs & Services, Library, เปิด Compute Engine API

ระวัง: GCP สร้างโปรเจกต์ชื่อ "My First Project" ให้อัตโนมัติ ตัวเลือกโปรเจกต์ที่มุมบนซ้ายของ Console มักค้างอยู่ที่อันนี้ เราเคยสร้าง service account, VPC และ VM ลงโปรเจกต์ผิดตัวมาแล้ว ให้ดูชื่อโปรเจกต์ก่อนกด Create ทุกครั้ง ถ้าของไปอยู่คนละโปรเจกต์แล้ว ไม่ต้องย้าย ให้เพิ่มสิทธิ์ข้ามโปรเจกต์ (cross-project IAM) แทน ดูส่วนที่ 7.3

### 6.2 Service Account (ไม่ใช้ JSON key)

IAM & Admin, Service Accounts, Create service account ชื่อ `zabbix-billing-reader` แล้วให้ role

- Compute Viewer (ที่โปรเจกต์)
- BigQuery Data Viewer และ BigQuery Job User (ที่โปรเจกต์ที่เก็บ dataset ของ billing export ในส่วนที่ 7)
- Billing Account Viewer (ที่ Billing account)

หลายบัญชีจะสร้าง JSON key ไม่ได้ เพราะ Organization Policy `iam.disableServiceAccountKeyCreation` บล็อกอยู่ อย่าพยายามไปปลดล็อก ให้ผูก service account เข้ากับ VM ตอนสร้าง VM (ข้อ 6.4) แล้ว library ของ Google จะใช้ Application Default Credentials ดึงสิทธิ์จาก VM เองโดยไม่ต้องมีไฟล์ key ใดๆ

### 6.3 Network และ Firewall

VPC network, VPC networks, Create VPC network

- Name: `vpc-zabbix-gcp`
- Subnet creation mode: Custom
- Subnet: ชื่อ `subnet-zabbix-proxy`, Region `us-central1`, IP range `10.1.1.0/24`

region ต้องเป็น us-central1, us-west1 หรือ us-east1 เท่านั้น ถึงจะอยู่ใน Always Free

VPC ใหม่ไม่มีกฎ ingress ที่เปิดไว้เลย ต้องสร้างเองที่ Firewall, Create firewall rule (Network เลือก `vpc-zabbix-gcp`, Direction Ingress, Action Allow)

| ชื่อ | Target tags | Source IPv4 ranges | Protocol/port |
|---|---|---|---|
| `fw-zabbix-gcp-allow` | `zabbix-proxy` | `<ON_PREM_PUBLIC_IP>/32` | tcp:10050-10051 |
| `fw-zabbix-gcp-ssh` | `zabbix-proxy` | `35.235.240.0/20` | tcp:22 |
| `fw-zabbix-target-allow` | `zabbix-target` | `10.1.1.3/32` (IP ภายในของ proxy) | tcp:10050 |
| `fw-zabbix-target-ssh` | `zabbix-target` | `35.235.240.0/20` | tcp:22 |
| `fw-zabbix-target-jmeter` (ตอนทำส่วนที่ 11 เท่านั้น) | `zabbix-target` | `<JMETER_PC_IP>/32` | tcp:5000 |

`35.235.240.0/20` คือช่วง IP ของ Identity-Aware Proxy (IAP) ที่ปุ่ม SSH ในหน้า Console ใช้เชื่อมเข้า VM ถ้าไม่มีกฎนี้ ปุ่ม SSH จะขึ้น "Connection via Cloud Identity-Aware Proxy Failed" เราเจอปัญหานี้และติดอยู่พักใหญ่ (ในชุดแรกเราตั้ง `fw-zabbix-gcp-ssh` เป็น 0.0.0.0/0 ซึ่งเปิดกว้างเกินความจำเป็น ถ้าเข้าเครื่องผ่านปุ่ม SSH ใน Console อย่างเดียว ใช้ช่วงของ IAP ก็พอ)

ถ้าใช้ agent แบบ active ให้เพิ่ม rule ให้ tag `zabbix-proxy` รับ tcp:10051 จาก `10.1.1.0/24` ด้วย

### 6.4 สร้าง VM สำหรับ Proxy

Compute Engine, VM instances, Create instance

- Name: `zabbix-proxy-gcp`
- Region `us-central1`, Machine type `e2-micro`
- Boot disk: Ubuntu 24.04 LTS, ชนิด Standard persistent disk, ขนาด 30 GB (ค่าเริ่มต้นของ Console มักเป็น Balanced ซึ่งไม่ฟรี ต้องเปลี่ยนเอง)
- Identity and API access: Service account เลือก `zabbix-billing-reader`, Access scopes เลือก "Allow full access to all Cloud APIs"
- Networking: Network tags ใส่ `zabbix-proxy`, Network interface เลือก `vpc-zabbix-gcp` / `subnet-zabbix-proxy`, External IPv4 เป็น Ephemeral

จดค่า External IP (เรียกว่า `<GCP_PROXY_PUBLIC_IP>`) และ Internal IP (ของเราคือ 10.1.1.3) แล้วกด SSH ในหน้า Console เพื่อเข้าเครื่อง

### 6.5 ติดตั้ง Proxy

ขั้นตอนและคำสั่งเหมือนส่วน 5.5 ทุกบรรทัด (ใช้ repo ของ ubuntu24.04, ติดตั้ง `zabbix-proxy-sqlite3 zabbix-agent2 zabbix-get zabbix-sender zabbix-sql-scripts`, สร้าง `/var/lib/zabbix`, นำเข้า `proxy.sql`, สร้าง PSK) ต่างกันที่ไฟล์ `/etc/zabbix/zabbix_proxy.conf`

```ini
Server=<ON_PREM_PUBLIC_IP>
Hostname=zabbix-proxy-gcp
ProxyMode=1
DBName=/var/lib/zabbix/zabbix_proxy.db

TLSAccept=psk
TLSConnect=psk
TLSPSKIdentity=PSK-GCP-Proxy
TLSPSKFile=/etc/zabbix/enc/proxy_psk.txt
```

ตั้งเป็น Passive ตั้งแต่ต้น ไม่ต้องลองผิดลองถูกแบบที่ทำกับ AWS ใช้ PSK คนละค่ากับ AWS (สร้างใหม่ด้วย `openssl rand -hex 32`)

ลงทะเบียนในหน้าเว็บเหมือน 5.6 โดยใช้ Proxy name `zabbix-proxy-gcp`, Address `<GCP_PROXY_PUBLIC_IP>`, PSK identity `PSK-GCP-Proxy`

### 6.6 สร้าง VM เป้าหมาย gcp-target-01

Create instance อีกตัว

- Name: `gcp-target-01`, Region `us-central1`, Machine type `e2-micro`
- Boot disk: Ubuntu 24.04 LTS แบบ Standard persistent disk
- Network tags: `zabbix-target`
- Network: `vpc-zabbix-gcp` / `subnet-zabbix-proxy` (ของเราได้ 10.1.1.4) และมี External IP แบบ Ephemeral

ข้อควรรู้: Always Free ให้ `e2-micro` เครื่องเดียว VM เครื่องที่สองคิดเงินตามชั่วโมง ใช้เสร็จให้ Stop

ติดตั้ง agent เหมือนส่วน 5.7 แต่ `/etc/zabbix/zabbix_agent2.conf` เป็น

```ini
Server=10.1.1.3
ServerActive=10.1.1.3
Hostname=gcp-target-01
```

ทดสอบจาก `zabbix-proxy-gcp`

```bash
zabbix_get -s 10.1.1.4 -p 10050 -k agent.ping
```

ได้ `1` แล้วเพิ่ม host ในหน้าเว็บ Host name `gcp-target-01`, Templates `Linux by Zabbix agent` + `Custom Linux Extended`, Host groups `GCP Compute Engine`, Interface Agent `10.1.1.4`:10050, Monitored by Proxy `zabbix-proxy-gcp`

Auto-Discovery ฝั่ง GCP ตั้งได้ด้วยวิธีเดียวกับส่วน 5.8 (IP range `10.1.1.1-254`, proxy `zabbix-proxy-gcp`, group `GCP Compute Engine`) แต่ในโปรเจกต์นี้เราไม่ได้ทดสอบ discovery ฝั่ง GCP ให้ครบ จึงไม่ยืนยันว่าใช้ได้

---

## 7. ดึงค่าใช้จ่ายจาก AWS และ GCP เข้า Zabbix

AWS กับ GCP ให้ข้อมูลบิลคนละทางกัน AWS มี Cost Explorer API เรียกได้ตรงๆ ส่วน GCP ไม่มี API แบบนั้น ทางที่ Google แนะนำคือให้ export ข้อมูลบิลลง BigQuery แล้วเขียน SQL ถาม สคริปต์สองตัวของเราจึงดึงข้อมูลคนละวิธี แต่ส่งเข้า Zabbix ด้วยรูปแบบเดียวกัน

### 7.1 สร้างของฝั่ง Zabbix ก่อนรันสคริปต์

ต้องทำข้อนี้ก่อนทุกอย่าง ถ้ารันสคริปต์ก่อนที่ host และ item จะมีอยู่ `zabbix_sender` จะตอบ `processed: 0; failed: N` ทุกครั้ง (เราเจอมาแล้ว)

สร้าง host ที่ Data collection, Hosts, Create host

| | AWS | GCP |
|---|---|---|
| Host name | `AWS-Cost-Monitor` | `GCP-Cost-Monitor` |
| Host groups | `Cost Monitoring` | `Cost Monitoring` |
| Monitored by | Proxy `zabbix-proxy-aws` | Proxy `zabbix-proxy-gcp` |
| Interfaces | ไม่ต้องใส่ | ไม่ต้องใส่ |

ในแต่ละ host สร้าง item ตัวแรก (Items, Create item)

| ช่อง | AWS | GCP |
|---|---|---|
| Name | `AWS Total Daily Cost` | `GCP Total Daily Cost` |
| Type | Zabbix trapper | Zabbix trapper |
| Key | `aws.cost.total` | `gcp.cost.total` |
| Type of information | Numeric (float) | Numeric (float) |
| Units | `USD` | `USD` |
| History storage period | Store up to `31d` | Store up to `31d` |

อย่าเลือก "Do not keep history" เพราะ Grafana จะไม่มีข้อมูลให้วาด

สร้าง Discovery rule (Discovery, Create discovery rule)

| ช่อง | AWS | GCP |
|---|---|---|
| Name | `AWS Cost Discovery` | `GCP Cost Discovery` |
| Type | Zabbix trapper | Zabbix trapper |
| Key | `aws.cost.discovery` | `gcp.cost.discovery` |

เปิด rule ที่สร้าง ไปแท็บ Item prototypes, Create item prototype

| ช่อง | AWS | GCP |
|---|---|---|
| Name | `AWS Cost - {#SERVICE}` | `GCP Cost - {#SERVICE}` |
| Type | Zabbix trapper | Zabbix trapper |
| Key | `aws.cost.service[{#SERVICE}]` | `gcp.cost.service[{#SERVICE}]` |
| Type of information | Numeric (float) | Numeric (float) |
| Units | `USD` | `USD` |
| History storage period | `31d` | `31d` |

รูปแบบชื่อ item ต้องเป็น `AWS Total Daily Cost`, `GCP Total Daily Cost`, `AWS Cost - ...` และ `GCP Cost - ...` ตามนี้เป๊ะๆ เพราะ panel ของ Grafana ค้นหาด้วยชื่อ

### 7.2 AWS: Cost Explorer

1. เปิดใช้ Cost Explorer: Billing and Cost Management, Cost Explorer, Launch Cost Explorer ข้อมูลชุดแรกใช้เวลาไม่เกิน 24 ชั่วโมง
2. IAM, Policies, Create policy เลือก JSON แล้ววาง

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["ce:GetCostAndUsage", "ce:GetCostForecast", "ce:GetDimensionValues"],
       "Resource": "*"
     }]
   }
   ```

   ตั้งชื่อ `ZabbixCostExplorerRead`
3. IAM, Users, Create user ชื่อ `zabbix-cost-reader` แนบ policy ข้างบน แล้วเข้าแท็บ Security credentials, Create access key เลือก use case เป็น "Application running outside AWS" เก็บ Access key ID กับ Secret access key ไว้ (อีกทางที่ปลอดภัยกว่าคือแนบ IAM role เข้า EC2 โดยตรง boto3 จะอ่านสิทธิ์เองโดยไม่ต้องมี key แต่เราใช้ access key)
4. บน zabbix-proxy-aws

   ```bash
   sudo apt install -y python3-pip
   pip3 install boto3 --break-system-packages

   mkdir -p ~/.aws
   nano ~/.aws/credentials
   ```

   ```ini
   [default]
   aws_access_key_id = <ACCESS_KEY_ID>
   aws_secret_access_key = <SECRET_ACCESS_KEY>
   ```

   ```bash
   nano ~/.aws/config
   ```

   ```ini
   [default]
   region = us-east-1
   ```

   ```bash
   chmod 600 ~/.aws/credentials
   ```

5. วางสคริปต์ [`scripts/aws_cost_aggregator.py`](scripts/aws_cost_aggregator.py) ไว้ที่ home ของ user (`nano ~/aws_cost_aggregator.py` แล้ววางเนื้อหา วิธีนี้ง่ายและเสี่ยงผิดน้อยกว่า scp ข้ามระบบปฏิบัติการ) และเตรียมไฟล์ log

   ```bash
   sudo touch /var/log/zabbix/aws_cost_aggregator.log
   sudo chown $USER:$USER /var/log/zabbix/aws_cost_aggregator.log
   ```

6. ทดสอบรัน

   ```bash
   python3 ~/aws_cost_aggregator.py
   tail -n 20 /var/log/zabbix/aws_cost_aggregator.log
   ```

   ใน log ต้องเห็นยอดรวมและบรรทัดจาก `zabbix_sender` ที่ลงท้ายด้วย `processed: N; failed: 0` ถ้ามี failed ให้ดูหัวข้อปัญหาข้อ `zabbix_sender processed: 0`

สคริปต์ทำสามอย่างในครั้งเดียว คือส่งยอดรวมของเมื่อวาน (วัน UTC) ไปที่ `aws.cost.total`, ส่งรายชื่อบริการที่มีค่าใช้จ่ายมากกว่า 0 ไปที่ `aws.cost.discovery` เพื่อให้ Zabbix สร้าง item ของแต่ละบริการ และส่งยอดแยกตามบริการไปที่ `aws.cost.service[...]` ปลายทางคือ `127.0.0.1:10051` ซึ่งเป็น proxy บนเครื่องเดียวกัน ไม่ใช่ Zabbix Server เพราะ IP ภายในของ server ติดต่อจากเครื่องบนอินเทอร์เน็ตไม่ได้

การรันครั้งแรกหลังสร้าง item prototype อาจเห็น failed เป็นยอดแยกตามบริการ เพราะ item ของแต่ละบริการยังไม่ถูกสร้างจาก discovery ในจังหวะที่ส่งค่า รอ 1 ถึง 2 นาทีแล้วรันซ้ำอีกครั้งจะผ่าน

### 7.3 GCP: BigQuery Billing Export

1. BigQuery console, เลือกโปรเจกต์, Create dataset ตั้ง Dataset ID `billing_export` เลือก Location แล้วกด Create
2. Billing, Billing export, แท็บ BigQuery export, ส่วน "Detailed usage cost" กด Edit settings เลือกโปรเจกต์และ dataset `billing_export` กด Save (ถ้าต้องการ Standard usage cost ด้วยเปิดได้ แต่สคริปต์ของเราอ่านตารางแบบ Detailed ชื่อขึ้นต้นด้วย `gcp_billing_export_resource_v1_`)
3. รอ 24 ถึง 48 ชั่วโมง ตารางจะเริ่มมีข้อมูล ข้อมูลที่เกิดก่อนเปิด export ไม่ถูกย้อนมาให้ เมื่อมีตารางแล้ว ดูชื่อตารางจริงใน BigQuery Explorer ใต้ dataset นั้น (จะมีบัญชี billing ของคุณต่อท้ายชื่อ)
4. ให้สิทธิ์ service account `zabbix-billing-reader` ที่โปรเจกต์ที่เก็บ dataset: IAM, Grant access, ใส่อีเมลของ service account, role `BigQuery Data Viewer` และ `BigQuery Job User` ข้อนี้ใช้ได้แม้ VM จะอยู่คนละโปรเจกต์กับ dataset สิทธิ์ข้ามโปรเจกต์ทำได้ ไม่ต้องย้ายอะไร
5. บน zabbix-proxy-gcp

   ```bash
   sudo apt install -y python3-pip
   pip3 install google-cloud-bigquery --break-system-packages
   ```

6. วางสคริปต์ [`scripts/gcp_cost_aggregator.py`](scripts/gcp_cost_aggregator.py) ไว้ที่ home (`nano` แล้ววาง) แล้วแก้ค่าสามตัวบนสุดของไฟล์

   ```python
   BQ_PROJECT = "your-gcp-project-id"        # โปรเจกต์ที่มี dataset
   BQ_DATASET = "billing_export"
   BQ_TABLE   = "gcp_billing_export_resource_v1_XXXXXX_XXXXXX_XXXXXX"   # ชื่อจริงจาก BigQuery Explorer
   ```

7. เตรียมไฟล์ log แล้วทดสอบ (ไม่ต้องมี key ไฟล์ใดๆ สคริปต์ใช้ service account ที่ผูกกับ VM)

   ```bash
   sudo touch /var/log/zabbix/gcp_cost_aggregator.log
   sudo chown $USER:$USER /var/log/zabbix/gcp_cost_aggregator.log
   python3 ~/gcp_cost_aggregator.py
   tail -n 20 /var/log/zabbix/gcp_cost_aggregator.log
   ```

หมายเหตุสองข้อเกี่ยวกับตัวเลขของ GCP

- สคริปต์รวมคอลัมน์ `cost` ซึ่งเป็นยอดก่อนหักเครดิต ถ้าบัญชีมี free trial credit หรือส่วนลด ยอดที่เห็นใน Zabbix จะสูงกว่ายอดที่ต้องจ่ายจริง ช่วงที่เราทำ ยอดรายวันของ GCP เคยขึ้นไปที่ราว 31 USD ซึ่งดูผิดปกติสำหรับ free tier เรายังไม่ได้ตรวจหาสาเหตุ (สงสัยว่าเป็น VM เกินโควตาฟรี ดิสก์ Balanced หรือยอดที่ยังไม่หักเครดิต) ถ้าต้องการยอดสุทธิ ลองเปลี่ยน `SUM(cost)` ใน query เป็น `SUM(cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))` เรายังไม่ได้ทดสอบ query นี้ในโปรเจกต์
- ข้อมูลใน BigQuery ตามหลังความจริงหลายชั่วโมงถึงหนึ่งวัน ยอดของ "เมื่อวาน" ที่ดึงตอนตี 2 อาจยังไม่ครบ

### 7.4 ตั้งให้รันทุกวัน

บน zabbix-proxy-aws

```bash
crontab -e
```

```
0 1 * * * /usr/bin/python3 /home/ubuntu/aws_cost_aggregator.py
```

บน zabbix-proxy-gcp (แก้ path ให้ตรง home ของ user บนเครื่องนั้น)

```
0 2 * * * /usr/bin/python3 /home/<USER>/gcp_cost_aggregator.py
```

เวลาในที่นี้เป็นเวลาไทย เพราะเราตั้ง timezone ของเครื่องเป็น `Asia/Bangkok` ไว้ตั้งแต่ต้น ตรวจด้วย `crontab -l` ลำดับเวลาของระบบทั้งหมดคือ 01:00 AWS, 02:00 GCP, 03:00 สรุปเข้า LINE (ส่วนที่ 10) ให้เว้นห่างกันแบบนี้ เพื่อให้สคริปต์สรุปมาอ่านค่าตอนที่ค่าถูกส่งเข้า Zabbix แล้ว

### 7.5 ดูผลใน Zabbix

Monitoring, Latest data, กรอง Hosts เป็น `AWS-Cost-Monitor` หรือ `GCP-Cost-Monitor` จะเห็น

- `AWS Total Daily Cost`: ยอดรวมของวันเมื่อวาน (วัน UTC)
- `AWS Cost - <ชื่อบริการ>`: ยอดแยกตามบริการ เช่น EC2 Compute, EC2 Other, VPC (item พวกนี้เกิดขึ้นเองจาก discovery)

ค่าจะอัปเดตวันละครั้งตามรอบ cron กราฟจึงมีจุดวันละจุด

ถ้าอยากดูกราฟใน Zabbix เอง ให้กดคำว่า Graph ที่ท้ายแถวของ item ใน Latest data หรือสร้างหน้าสรุปที่ Dashboards, Create dashboard, Add widget เลือก Graph แล้วตั้ง Data set เป็น host `AWS-Cost-Monitor` / `GCP-Cost-Monitor` และ item pattern `*Cost*`

---

## 8. Grafana

Zabbix กราฟได้พื้นฐาน แต่เรารวมข้อมูลจากสามฝั่งให้อยู่ในหน้าเดียวและจัดหน้าตาเองไม่ได้ จึงใช้ Grafana ติดตั้งบนเครื่องเดียวกับ Zabbix Server

### 8.1 ติดตั้ง

บน Zabbix Server

```bash
sudo apt install -y apt-transport-https software-properties-common wget
sudo mkdir -p /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
sudo chmod 644 /etc/apt/keyrings/grafana.asc
echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
sudo apt update
sudo apt install -y grafana
sudo systemctl enable --now grafana-server
```

เปิด `http://172.16.46.104:3000` ล็อกอินด้วย `admin` / `admin` ระบบจะบังคับให้เปลี่ยนรหัสผ่าน

### 8.2 ติดตั้งปลั๊กอิน Zabbix

```bash
sudo grafana cli plugins install alexanderzobnin-zabbix-app
sudo systemctl restart grafana-server
```

เข้า Grafana ไปที่ Administration, Plugins and data, Plugins ค้นหา "Zabbix" เข้าไปแล้วกด Enable

### 8.3 สร้างผู้ใช้สำหรับ Grafana ฝั่ง Zabbix

ส่วนนี้เราพลาดบ่อยที่สุด สิทธิ์ใน Zabbix ตั้งที่ระดับ User group ไม่ใช่ที่ตัว user (แท็บ Permissions ของ user มีแค่ Role) และ Role ชื่อ Guest ปิดการเรียก API ทั้งหมด

1. Users, User groups, Create user group ชื่อ `Grafana Readers` ไปแท็บ Host permissions กด Select เลือก host group `Linux servers`, `AWS EC2`, `GCP Compute Engine`, `Cost Monitoring` ตั้ง Permission เป็น Read แล้ว Add
2. Users, Users, Create user ชื่อ `grafana-viewer` ใส่รหัสผ่าน ช่อง Groups เลือก `Grafana Readers` แท็บ Permissions ช่อง Role เลือก `User role` (ห้ามเลือก Guest role) แล้ว Add
3. Users, API tokens, Create API token ตั้งชื่อ เลือก User เป็น `grafana-viewer` เอาเครื่องหมายถูกตรง Set expiration date and time ออก (หรือตั้งวันหมดอายุให้ไกลพอ) กด Add แล้ว copy token ทันที Zabbix แสดงให้ดูครั้งเดียว

ถ้าเพิ่ม host group ใหม่ในอนาคต ต้องกลับมาเพิ่มใน `Grafana Readers` ด้วย

### 8.4 เพิ่ม Data source

Grafana, Connections, Data sources, Add data source เลือก Zabbix

- URL: `http://172.16.46.104/zabbix/api_jsonrpc.php` (ต้องมี `/zabbix/` ไม่งั้นจะได้ 404 หรือ "Could not connect to given url")
- Zabbix API details: ใช้ API token แล้ววาง token จากข้อ 8.3
- กด Save & test ต้องขึ้นว่าเชื่อมต่อสำเร็จ

ถ้า test ผ่านแต่ panel บอกว่า "No permissions to call hostgroup.get" แปลว่า user ยังเป็น Guest role

### 8.5 นำเข้า Dashboard

ไฟล์ทั้งหมดอยู่ในโฟลเดอร์ [`grafana/`](grafana/) สร้างด้วย Grafana v13 (schema `dashboard.grafana.app/v2`) ถ้า Grafana ของคุณเก่ากว่านี้มาก import อาจไม่ผ่าน ให้สร้าง panel เองตามข้อ 8.6

ไฟล์ JSON ผูกกับ data source ผ่านค่า uid ของ data source ตัวเดิมของเรา (`cfscfs9z76e4gf`) ซึ่งในเครื่องของคุณจะเป็นค่าอื่น ต้องแทนที่ก่อน import

1. หา uid ของ data source ของคุณ: Connections, Data sources, คลิกที่ data source Zabbix แล้วดู URL บนเบราว์เซอร์ จะเป็น `.../connections/datasources/edit/<uid>` ส่วนท้ายนั้นคือ uid
2. แทนที่ในไฟล์ทั้งหมด

   ```bash
   cd grafana
   sed -i 's/cfscfs9z76e4gf/<YOUR_DATASOURCE_UID>/g' *.json
   ```

3. Dashboards, New, Import, Upload dashboard JSON file เลือกไฟล์ แล้วกด Import ทำทีละไฟล์

เริ่มจาก `Hybrid_Cloud_Executive_Overview.json` เพราะเป็นหน้าหลักที่ใช้เดโม

| ไฟล์ | แสดงอะไร |
|---|---|
| `Hybrid_Cloud_Executive_Overview.json` | หน้าเดียวรวม 9 panel: สถานะของ 3 environment, กราฟเทียบ Cost กับ Performance, ค่าใช้จ่ายแยกตามบริการของ AWS และ GCP, กราฟ CPU / Memory / Network In ของทั้งสามฝั่งในกราฟเดียว |
| `Hybrid_Cloud_Cost_and_Performance_Dashboard.json` | มุมมองค่าใช้จ่าย AWS และ GCP คู่กัน พร้อม CPU |
| `ec2-target-01.json`, `gcp-target-01.json`, `Zabbix_Agent_On_Prem.json` | รายละเอียดรายเครื่อง: CPU, Memory, Disk, Network, Load average, Zombie process, Uptime, Agent availability |

ข้อสังเกตหลัง import

- panel ค้นหา host ด้วยชื่อ ถ้าชื่อ host ของคุณไม่ตรงกับตารางในส่วนที่ 1 panel จะว่าง
- panel Network ค้นหา item ตามชื่อ interface ของแต่ละเครื่อง ซึ่งไม่เหมือนกัน ดูชื่อจริงด้วย `ip -br a` ในไฟล์ของเรา AWS เป็น `ens5` และ on-prem เป็น `enp1s0f0` ส่วน GCP ตั้งไว้เป็น `ens5` เหมือน AWS ซึ่งเรายังไม่ได้ยืนยันกับเครื่องจริง ถ้า VM ของคุณใช้ชื่ออื่น (เครื่องบน GCP มักเป็น `ens4`) ให้เปิด Edit ที่ panel แล้วเปลี่ยนชื่อ item ให้ตรง
- panel กราฟรวมสามฝั่งในกราฟเดียว ถ้าชื่อเส้นซ้ำกัน legend จะแยกไม่ออก เราแก้ด้วย field override แบบ "by query refId" แล้วตั้ง displayName ให้แต่ละ query แทนการอ้างอิงด้วยชื่อ series
- ชื่อ item "Load average (1m avg)", "(5m avg)", "(15m avg)" มาจาก template `Linux by Zabbix agent` ถ้า panel Load average ว่างให้เทียบชื่อใน Monitoring, Latest data

### 8.6 สร้าง panel เอง (กรณีนำเข้าไม่ได้ หรืออยากเพิ่ม)

1. Dashboards, New dashboard, Add visualization, เลือก data source Zabbix
2. ช่อง Query type เลือก Metrics (ตัวเลือกอื่นคือ Text, Item ID, Triggers, Problems ไม่ใช้กับกราฟตัวเลข)
3. ช่อง Group, Host, Item เลือกตามลำดับ ตัวอย่าง

   | panel | Group | Host | Item |
   |---|---|---|---|
   | CPU ของ AWS | `AWS EC2` | `ec2-target-01` | `CPU utilization` |
   | ค่าใช้จ่ายรวม AWS | `Cost Monitoring` | `AWS-Cost-Monitor` | `AWS Total Daily Cost` |
   | ค่าใช้จ่ายแยกบริการ GCP | `Cost Monitoring` | `GCP-Cost-Monitor` | `/GCP Cost - .*/` (ขึ้นต้นและลงท้ายด้วย / คือ regex) |

4. ฝั่งขวา เลือก Visualization (Time series สำหรับ CPU, Stat หรือ Bar gauge สำหรับค่าใช้จ่าย) แล้วตั้ง Standard options, Unit เป็น Percent (0-100) สำหรับ CPU หรือ Currency, Dollars สำหรับค่าใช้จ่าย
5. ตั้งช่วงเวลาที่มุมบนขวา ค่าใช้จ่ายมีจุดวันละจุด ควรดู Last 7 days ขึ้นไป

ถ้า panel ขึ้น "No data" ทั้งที่ใน Zabbix Latest data มีค่า ให้ตรวจ 3 อย่างตามลำดับ (1) item นั้นตั้ง History storage period เป็น Do not keep history หรือเปล่า (2) host group ของ item นั้นอยู่ใน Host permissions ของ `Grafana Readers` ไหม (3) ช่วงเวลาที่เลือกกว้างพอที่จะครอบคลุมจุดข้อมูลไหม (item ที่ส่งวันละครั้งจะว่างถ้าเลือก Last 15 minutes)

---

## 9. แจ้งเตือนเข้า LINE

LINE Notify ปิดให้บริการไปแล้ว เราจึงใช้ LINE Messaging API แทน (ในเอกสารออกแบบช่วงต้นโปรเจกต์เรายังเขียนว่าใช้ LINE Notify ซึ่งต้องถือว่าเปลี่ยนแผนกลางทาง)

### 9.1 สร้าง LINE Official Account และเปิด Messaging API

ลำดับสำคัญ ต้องสร้าง Official Account ก่อนแล้วค่อยเปิด Messaging API ถ้าไปสร้าง channel จาก LINE Developers Console ตรงๆ จะไม่เจอตัวเลือก Messaging API

1. สร้าง LINE Official Account ที่ https://manager.line.biz ด้วยบัญชี LINE ของตัวเอง
2. ใน manager.line.biz เปิดบัญชีที่สร้าง ไปที่ Settings, Messaging API กดเปิดใช้ และสร้างหรือเลือก Provider ตามที่ถาม
3. ที่หน้า Response settings ปิด Greeting message และ Auto-response เพื่อไม่ให้บอทตอบกลับเอง
4. เข้า https://developers.line.biz/console/ เลือก Provider และ Channel ที่ตรงกับบัญชีนี้ แท็บ Messaging API เลื่อนลงไปที่ Channel access token (long-lived) กด Issue แล้ว copy เก็บไว้
5. ใช้มือถือสแกน QR code ในหน้าเดียวกันเพื่อเพิ่มบอทเป็นเพื่อน ถ้าไม่ทำข้อนี้ข้อความ broadcast จะไม่มาถึงเรา

เราใช้ API แบบ Broadcast (ส่งหาเพื่อนทุกคนของบัญชี) เพราะไม่ต้องหา User ID รายคน และไม่ต้องมี webhook รับข้อความขาเข้า ซึ่ง Zabbix Server ของเราไม่มี endpoint HTTPS สาธารณะอยู่แล้ว ข้อเสียคือทุกคนที่เพิ่มบอทจะได้ข้อความเหมือนกัน และแผนฟรีมีโควตาข้อความต่อเดือนจำกัด ดูโควตาจริงในหน้า Plan ของ Official Account

### 9.2 สร้าง Media type ใน Zabbix

Alerts, Media types, Create media type

- Name: `LINE Messaging API`
- Type: Webhook
- Parameters (Add สามรายการ)
  - `token` = Channel access token ที่ copy ไว้
  - `subject` = `{ALERT.SUBJECT}`
  - `message` = `{ALERT.MESSAGE}`
- Script วางโค้ดนี้

```javascript
try {
    var params = JSON.parse(value);
    var req = new HttpRequest();
    req.addHeader('Content-Type: application/json');
    req.addHeader('Authorization: Bearer ' + params.token);

    var text = params.subject + '\n' + params.message;
    var payload = JSON.stringify({ messages: [{ type: 'text', text: text }] });

    var resp = req.post('https://api.line.me/v2/bot/message/broadcast', payload);
    var code = req.getStatus();
    if (code < 200 || code >= 300) {
        throw 'HTTP ' + code + ': ' + resp;
    }
    return 'OK';
} catch (error) {
    Zabbix.log(4, '[LINE Webhook] ' + error);
    throw 'LINE notification failed: ' + error;
}
```

แท็บ Message templates เพิ่มสองแบบ

| Message type | Subject | Message |
|---|---|---|
| Problem | `Problem: {EVENT.NAME}` | `Host: {HOST.NAME}` ขึ้นบรรทัดใหม่ `Severity: {EVENT.SEVERITY}` ขึ้นบรรทัดใหม่ `Time: {EVENT.DATE} {EVENT.TIME}` |
| Problem recovery | `Resolved: {EVENT.NAME}` | `Host: {HOST.NAME}` ขึ้นบรรทัดใหม่ `Duration: {EVENT.DURATION}` |

(ในช่อง Message พิมพ์ขึ้นบรรทัดใหม่จริงด้วยปุ่ม Enter ไม่ต้องพิมพ์ `\n`)

กด Add แล้วทดสอบ ที่รายการ Media types กดคำว่า Test ท้ายแถว `LINE Messaging API` ใส่ token, subject และ message ทดลองแล้วกด Test ข้อความต้องเด้งเข้า LINE บนมือถือ

### 9.3 ผู้รับ

1. Users, User groups, Create user group ชื่อ `Alert Recipients` แท็บ Host permissions เลือก host group ทั้งหมดที่ใช้ในโปรเจกต์ (`Linux servers`, `AWS EC2`, `GCP Compute Engine`, `Cost Monitoring`) สิทธิ์ Read ผู้รับต้องมีสิทธิ์อ่าน host นั้นจึงจะได้รับแจ้งเตือนจาก host นั้น
2. Users, Users, Create user ตั้งชื่อ เช่น `line-alert` เลือก Groups เป็น `Alert Recipients` แท็บ Permissions ใส่ Role เป็น `User role`
3. แท็บ Media กด Add เลือก Type `LINE Messaging API` ช่อง Send to ใส่อะไรก็ได้ที่ไม่ว่าง (เช่น `-` เพราะ Broadcast ไม่ใช้ค่านี้) ติ๊ก Use if severity เฉพาะ Warning ขึ้นไป แล้วกด Add

### 9.4 Action สำหรับ Trigger

Alerts, Actions, Trigger actions, Create action

- Name: `Send alerts to LINE`
- Conditions: Add เลือก Trigger severity, เงื่อนไข "is greater than or equals", ค่า Warning เงื่อนไขเดียวเท่านั้น
- Operations: Add, Send message, User groups `Alert Recipients`, Send only to `LINE Messaging API`
- Recovery operations: Add, Notify all involved (เพื่อให้ได้ข้อความตอนปัญหาหายด้วย)

เราตั้งใจไม่ใส่เงื่อนไข Host group ใน Action นี้ ผลคือ host ใดก็ตามที่เพิ่มเข้ามาทีหลัง ไม่ว่าจะเป็นเครื่องที่ discovery เพิ่มให้หรือเพิ่มด้วยมือ ถ้ามี trigger ระดับ Warning ขึ้นไปก็แจ้งเตือนเข้า LINE ทันที ไม่ต้องกลับมาแก้ Action อีก เพราะอย่างนี้ลำดับที่ทำ GCP กับทำแจ้งเตือนจะสลับกันก็ได้ ไม่ต้องย้อนมาตั้งซ้ำ (เงื่อนไขเดียวที่ต้องดูแลคือ host group ใหม่ต้องถูกเพิ่มใน `Alert Recipients`)

### 9.5 ทดสอบจริง

บน ec2-target-01 หยุด agent

```bash
sudo systemctl stop zabbix-agent2
```

ประมาณ 3 นาทีต่อมา trigger "Zabbix agent is not available" จะทำงาน (ความรุนแรงระดับ Average) และข้อความเข้า LINE สั่ง `sudo systemctl start zabbix-agent2` แล้วรอข้อความ Resolved

---

## 10. สรุปค่าใช้จ่ายรายวันเข้า LINE

ส่วนนี้ส่งข้อความสรุปยอด AWS และ GCP ของวันก่อนหน้าทุกวัน ไม่ว่ายอดจะเกินเกณฑ์หรือไม่ ทำงานแยกจาก Trigger Action ในข้อ 9.4 (เป็น cron ไม่ใช่การแจ้งเตือนของ Zabbix) สคริปต์อ่านค่าล่าสุดของ `aws.cost.total` และ `gcp.cost.total` ผ่าน Zabbix API แล้วส่ง Broadcast ผ่าน LINE

### 10.1 สร้างผู้ใช้ API สำหรับสคริปต์

เหมือนข้อ 8.3 แต่แยกผู้ใช้ออกมา

1. สร้าง user ชื่อ `cost-digest-reader` ใน User group ที่มี Read บน host group `Cost Monitoring` (ใช้ `Grafana Readers` ได้) Role เป็น `User role`
2. Users, API tokens, Create API token สำหรับ user นี้ แล้ว copy token

### 10.2 ติดตั้งสคริปต์บน Zabbix Server

```bash
mkdir -p ~/cost-digest && cd ~/cost-digest
nano daily_cost_digest.py      # วางเนื้อหาจาก scripts/daily_cost_digest.py
python3 -c "import requests" || sudo apt install -y python3-requests
sudo touch /var/log/zabbix/daily_cost_digest.log
sudo chown $USER:$USER /var/log/zabbix/daily_cost_digest.log
```

แก้สามค่าบนสุดของไฟล์

```python
ZABBIX_URL = "http://172.16.46.104/zabbix/api_jsonrpc.php"
ZABBIX_API_TOKEN = "PASTE_ZABBIX_API_TOKEN_HERE"
LINE_CHANNEL_ACCESS_TOKEN = "PASTE_LINE_CHANNEL_ACCESS_TOKEN_HERE"
```

`ZABBIX_URL` ต้องมี `/zabbix/` ถ้าลืมจะได้ HTTP 404 (เราเจอมาแล้ว) แล้วจำกัดสิทธิ์ไฟล์เพราะมี token อยู่ข้างใน

```bash
chmod 600 daily_cost_digest.py
python3 daily_cost_digest.py
tail -n 10 /var/log/zabbix/daily_cost_digest.log
```

ข้อความต้องเข้า LINE ถ้า log ว่างเปล่าแต่สคริปต์ไม่ error ให้ดูหัวข้อปัญหาเรื่อง `logging.basicConfig`

### 10.3 ตั้ง cron

```bash
crontab -e
```

```
0 3 * * * /usr/bin/python3 /home/<USER>/cost-digest/daily_cost_digest.py
```

### 10.4 ข้อความที่ได้หมายถึงอะไร

- ตัวเลขเป็นยอดของวันเดียว ไม่ใช่ยอดสะสมตั้งแต่ต้นเดือน เพราะสคริปต์ aggregator ดึงเฉพาะ "เมื่อวาน" แล้วเขียนทับค่าเดิมทุกวัน
- ป้ายวันที่ในข้อความเป็นวันตามเวลา UTC ของข้อมูลที่ดึง (aggregator ใช้วัน UTC เช่นกัน และ cron ทั้งสามตัวอยู่ในวัน UTC เดียวกัน) วัน UTC หนึ่งวันคือ 07:00 ถึง 07:00 ของวันถัดไปตามเวลาไทย เช่น ข้อความที่ส่งเช้าวันที่ 19 ตุลาคม จะเขียนวันที่ 17 ตุลาคม UTC
- บรรทัดล่างสุดคือเวลาที่ค่านั้นถูกส่งเข้า Zabbix ล่าสุด ใช้ตรวจว่าสคริปต์ตัวต้นทางยังรันอยู่หรือเปล่า

---

## 11. ทดสอบโหลดด้วย JMeter

เป้าหมายของส่วนนี้ คือทำให้กราฟ CPU, Memory ของทั้งสามเครื่องขยับให้เห็นระหว่างเดโม โดยให้ JMeter ยิงเข้าเครื่อง

Zabbix Agent รายงานค่าอย่างเดียว ไม่มีช่องทางให้ JMeter ส่งงานเข้าไปได้ เราจึงเขียนแอป Flask เล็กๆ ลงบนแต่ละเครื่อง มี endpoint `/load` ที่เผา CPU ด้วยการคำนวณ SHA-256 วนไปเรื่อยๆ ตามจำนวนวินาทีที่ขอ JMeter ยิง endpoint นี้พร้อมกันหลาย thread CPU ของเครื่องจึงสูงขึ้น และ Zabbix ก็เก็บค่าจาก item `CPU utilization` เดิมที่ dashboard ใช้อยู่แล้ว ไม่ต้องตั้งอะไรเพิ่มฝั่ง Zabbix

### 11.1 ติดตั้งแอปบนทั้งสามเครื่อง

ทำบน ec2-target-01, gcp-target-01 และเครื่อง on-prem 172.16.46.92 ทีละเครื่อง

```bash
# เครื่อง Ubuntu 24.04 (AWS, GCP)
sudo apt install -y python3-pip
pip3 install flask --break-system-packages

# เครื่อง Ubuntu 22.04 (on-prem)
sudo apt install -y python3-pip
pip3 install flask
```

วางโค้ดจาก [`scripts/cpu_load_app.py`](scripts/cpu_load_app.py) ลงไฟล์ในเครื่อง (`nano cpu_load_app.py` แล้ววาง) แล้วรัน

```bash
nohup python3 cpu_load_app.py > flask.log 2>&1 &
curl http://127.0.0.1:5000/
curl "http://127.0.0.1:5000/load?seconds=1"
```

อย่างแรกต้องตอบ `{"message":"CPU load generator is running","status":"ok"}` อย่างที่สองใช้เวลาประมาณ 1 วินาทีแล้วตอบ `status: done` ติดตั้ง flask ด้วย user เดียวกับที่รันแอป ถ้าติดตั้งด้วย `sudo` แล้วรันแบบ user ธรรมดาจะได้ `ModuleNotFoundError: No module named 'flask'` ใน `flask.log`

### 11.2 เปิด port 5000 ให้เครื่องที่รัน JMeter

หา Public IP ของเครื่องที่รัน JMeter (เรียกว่า `<JMETER_PC_IP>`) แล้วเปิดเฉพาะ IP นี้

- AWS: เพิ่ม inbound rule ใน `sg-zabbix-target` Custom TCP 5000 source `<JMETER_PC_IP>/32`
- GCP: สร้าง firewall rule `fw-zabbix-target-jmeter` ตามตารางในข้อ 6.3
- On-prem: ไม่ต้องตั้งฝั่ง cloud ถ้าเครื่องเปิด ufw ไว้ให้สั่ง `sudo ufw allow 5000/tcp`

ทดสอบจากเครื่องที่รัน JMeter ว่าเข้าถึงได้ (IP ของ AWS และ GCP คือ Public IP ปัจจุบัน ซึ่งเปลี่ยนทุกครั้งที่ Stop แล้ว Start เครื่อง ต้องตรวจทุกครั้งก่อนยิง)

```bash
curl http://<AWS_TARGET_PUBLIC_IP>:5000/
curl http://<GCP_TARGET_EXTERNAL_IP>:5000/
curl http://172.16.46.92:5000/
```

### 11.3 รันแผน JMeter สำหรับเดโม

ติดตั้ง Java และ Apache JMeter จาก https://jmeter.apache.org/download_jmeter.cgi แล้วเปิดไฟล์ [`load-testing/hybrid_cloud_load_test.jmx`](load-testing/hybrid_cloud_load_test.jmx)

1. คลิก Test Plan บนสุด ที่ตาราง User Defined Variables แก้ `AWS_HOST` เป็น Public IP ของ ec2-target-01, `GCP_HOST` เป็น External IP ของ gcp-target-01, `ONPREM_HOST` เป็น `172.16.46.92`
2. แผนมี Thread Group สามกลุ่ม (AWS, GCP, On-Prem) แต่ละกลุ่มวน GET ไปที่ `/load` ของเครื่องตัวเอง ค่าในไฟล์เป็น 15 thread, ramp-up 5 วินาที, ระยะเวลา 300 วินาที ตอนซ้อมเดโมเราปรับเป็น 100 thread และ 600 วินาที ให้กราฟนิ่งนานพอจะอธิบายได้
3. กดปุ่มลูกศรเขียว Start

สิ่งที่ควรรู้ก่อนเดโมจริง

- เริ่มยิงก่อนเริ่มพูดถึงกราฟ Performance อย่างน้อย 5 ถึง 6 นาที กราฟเริ่มขยับหลังเริ่มยิงประมาณ 1 ถึง 2 นาที เพราะ agent รายงานทุกประมาณ 1 นาที และยอดสูงสุดจะเห็นชัดเมื่อผ่านไป 5 ถึง 6 นาที
- เปิดหน้า Executive Overview ใน Grafana ตั้งช่วงเวลา Last 15 minutes และ refresh ทุก 5 หรือ 10 วินาที
- CPU จะไม่ขึ้นถึง 100% ซึ่งเป็นเรื่องปกติ ไม่ใช่บั๊ก แอป Flask ใช้ได้ประมาณ 1 core เพราะ Python GIL ดังนั้นเพดานของเครื่องคือ 100 หารด้วยจำนวน core เครื่อง AWS (2 vCPU) จึงอยู่ราว 50% และเครื่อง on-prem 4 core อยู่ราว 25% ผลที่เราได้ตอนซ้อมเดโมด้วย 100 thread 600 วินาที ค่าสูงสุดของ AWS 51.8%, GCP 69.3%, On-Prem 26.2% ค่าของ GCP เกินเพดานทางทฤษฎี 50% เรายังไม่ได้หาสาเหตุ (e2-micro เป็นเครื่องแบบ shared-core ซึ่งการรายงาน CPU ต่างจากเครื่องปกติ)
- เครื่อง GCP e2-micro เป็นแบบ burstable/shared-core เมื่อใช้ CPU เกินระดับพื้นฐานไปสักพักจะถูกจำกัด กราฟจึงมักเป็นแบบพุ่งแล้วตก ไม่ใช่ที่ราบ
- แผงค่าใช้จ่ายจะไม่ขยับระหว่างเดโม เพราะ Cost Explorer และ BigQuery export ล่าช้าราว 24 ชั่วโมง ควรอธิบายให้ผู้ชมเข้าใจว่าเป็นธรรมชาติของระบบบิล ไม่ใช่ความผิดของ dashboard
- เผื่อเน็ตหรือ IP มีปัญหาระหว่างเดโม ควรอัดวิดีโอสำรองไว้ล่วงหน้า

ถ้าเครื่อง t3 มีโหมด credit เป็น Unlimited (ค่าเริ่มต้นของ t3 คือเปิด) การใช้ CPU สูงต่อเนื่องอาจมีค่า surplus credit เล็กน้อยเกิดขึ้น ก่อนยิงโหลดนานๆ ให้ตรวจ Credit specification ของ instance และตรวจ Budget Alert ก่อน

### 11.4 ชุด Test Case สำหรับวัดผลจริงจัง

นอกจากแผนเดโมแล้ว เราออกแบบตารางทดสอบ 8 scenario ยิงทั้งสามเครื่องพร้อมกันด้วยค่าเดียวกัน เพื่อเทียบการรับโหลด (Error, Response time), เวลาที่ Zabbix/Grafana เห็นโหลด, agent หลุดไหม และการกลับสู่ปกติหลังหยุด ไฟล์อยู่ใน [`load-testing/`](load-testing/)

- `hybrid_cloud_loadtest_scenarios.jmx` แผน JMeter ที่ทุกค่ารับจาก parameter บรรทัดคำสั่ง
- `load_test_cases.xlsx` ตารางออกแบบ ประกอบด้วยแท็บ Instructions, Targets, Test Cases, Results Log (กรอกผล มีสูตรตัดสิน PASS/FAIL ให้) และ Summary

| รหัส | Scenario | Thread | Ramp-up (วินาที) | ระยะเวลา (วินาที) | Think time (วินาที) | จุดประสงค์ |
|---|---|---|---|---|---|---|
| LT-01 | Smoke | 1 | 1 | 120 | 6 | ตรวจว่าเส้นทาง JMeter, Flask, Zabbix, Grafana ครบ และเก็บ baseline |
| LT-02 | Light load | 2 | 5 | 300 | 6 | โหลดเบา |
| LT-03 | Medium load | 3 | 5 | 300 | 6 | โหลดกลาง |
| LT-04 | Saturation point | 4 | 5 | 300 | 6 | โหลดรวมแตะเพดาน 1 core พอดี |
| LT-05 | Overload | 8 | 5 | 300 | 6 | ขอเกินเพดาน ดู CPU ค้างที่เพดานและ Response time ที่เพิ่ม |
| LT-06 | Stress | 100 | 60 | 300 | 0 | ค่าเดียวกับเดโมสด ดู Error, Response time, Memory |
| LT-07 | Spike and recovery | 100 | 2 | 120 | 0 | ขึ้นเต็มใน 2 วินาทีแล้วหยุด วัดเวลากลับสู่ปกติ |
| LT-08 | Soak | 3 | 5 | 1800 | 6 | 30 นาที ดูการ throttle ของ burstable, memory ค่อยๆ โต, agent หลุดไหม |

ทุก scenario ใช้เวลาเผา CPU ต่อ request 2 วินาที (`-Jseconds=2`) Think time คุมสัดส่วนเวลาที่โหลดทำงาน เช่น 2 วินาทีเผา 6 วินาทีพักคือใช้ CPU 1 core ราว 25% ต่อ thread คำสั่งของแต่ละ scenario สร้างอัตโนมัติอยู่ในคอลัมน์สุดท้ายของแท็บ Test Cases หน้าตาประมาณนี้ (ตัวอย่าง LT-02)

```bash
jmeter -n -t hybrid_cloud_loadtest_scenarios.jmx \
  -Jthreads=2 -Jrampup=5 -Jduration=300 -Jseconds=2 -Jthink_ms=6000 \
  -Jaws_host=<AWS_TARGET_PUBLIC_IP> -Jgcp_host=<GCP_TARGET_EXTERNAL_IP> -Jonprem_host=172.16.46.92 \
  -l results_LT-02.jtl -e -o report_LT-02
```

วิธีใช้ตาราง: ใส่ IP ปัจจุบันและจำนวน CPU จริงของแต่ละเครื่อง (รัน `nproc` บนเครื่อง ค่า 4 สำหรับ on-prem ในไฟล์เป็นค่าตั้งต้นที่เดาจากผลเดโม ต้องยืนยัน) ในแท็บ Targets, รัน scenario ตามลำดับโดยรอ cooldown ตามตาราง (t3.micro และ e2-micro เป็น burstable ถ้ารันติดกัน credit จะหมดหรือถูก throttle ผลจะเพี้ยน), เปิดรายงาน `report_<รหัส>/index.html` อ่านตาราง Statistics แยกตาม label แล้วดู CPU, Memory สูงสุดจาก Grafana กรอกลงแท็บ Results Log (ช่องสีเหลือง) ส่วน PASS/FAIL กับ Summary คำนวณเอง

ข้อควรระวัง: ไฟล์ `hybrid_cloud_loadtest_scenarios.jmx` และตารางนี้เราสร้างไว้แล้ว แต่ยังไม่ได้เปิดรันใน JMeter และแถวใน Results Log มีแค่แถวตัวอย่าง ไม่มีผลจริง ถ้าจะใช้ ให้รัน LT-01 ก่อนเพื่อเช็คว่าแผนทำงาน แล้วปรับเกณฑ์ Max RT ในตารางให้ตรงกับ baseline จริงของแต่ละเครื่อง

### 11.5 เก็บกวาดหลังทดสอบ

```bash
pkill -f cpu_load_app.py
```

ทำทุกเครื่อง แล้วลบ rule port 5000 ที่เปิดไว้ใน Security Group และ Firewall

### 11.6 เช็คลิสต์ก่อนเดโมจริง

ไล่ตามนี้ก่อนวันเดโมหรือก่อนอัดวิดีโอ

1. Monitoring, Hosts ทุก host ป้าย ZBX เขียว และ Administration, Proxies คอลัมน์ Last seen ของทั้งสอง proxy เป็นหน่วยวินาที
2. Monitoring, Latest data ของ `AWS-Cost-Monitor` และ `GCP-Cost-Monitor` มีค่าของเมื่อวาน
3. Public IP ของ ec2-target-01 และ gcp-target-01 ที่ใช้ใน JMeter เป็นค่าปัจจุบัน และ `curl http://<IP>:5000/` ตอบ ok ทั้งสามเครื่อง
4. Security Group และ Firewall rule port 5000 ยังใช้ IP ของเครื่องที่รัน JMeter ตอนนี้
5. ทดสอบ Media type (ข้อ 9.2) ว่าข้อความเข้า LINE
6. Grafana หน้า Executive Overview แสดงข้อมูลครบ ไม่มี panel ว่าง

---

## 12. การทดลองเรื่องค่าใช้จ่าย (Cloud Cost Experiment)

ส่วนนี้เปลี่ยนชั้น Cost Visibility จากหน้าจอที่โชว์ตัวเลขเฉยๆ ให้ถูกใช้ตอบคำถามเปรียบเทียบจริง คือเมื่อทำการกระทำแบบเดียวกันบน AWS และ GCP พร้อมกัน ค่าใช้จ่ายของแต่ละฝั่งเพิ่มเท่าไร และระบบบิลของใครรายงานผลเร็วกว่ากัน เป็นสองค่าที่แยกกันวัด คือขนาดของการเพิ่ม (magnitude) กับเวลาที่ระบบรายงานให้เห็น (detection latency)

เอกสารและตารางอยู่ใน [`planning-docs/`](planning-docs/)

- `Cost_Test_Case_Protocol.docx` แผนการทดลอง ตัวเลือก test case เช็คลิสต์ความปลอดภัยด้านงบ ขั้นตอน และแผน rollback
- `cost_test_case_results.xlsx` ตารางบันทึกผล มีแท็บ Instructions, Test Log (กรอกผลดิบ) และ Comparison Summary (คำนวณเปรียบเทียบ AWS กับ GCP ด้วยสูตร)

ตัวเลือก test case

| รหัส | การกระทำ | วัดอะไร | ความเสี่ยงด้านงบ |
|---|---|---|---|
| TC-A Compute resize | เปลี่ยนขนาด instance จาก micro เป็น small พร้อมกันสอง cloud 1 ชั่วโมงแล้วเปลี่ยนกลับ | ค่า compute ต่อชั่วโมง | ต่ำมาก (ไม่กี่เซนต์) |
| TC-B Storage | เพิ่มดิสก์ 10 GB ทิ้งไว้ 24 ชั่วโมงแล้วลบ | ค่า storage ต่อวัน | ต่ำ (เศษเซนต์) |
| TC-C Network egress | ดาวน์โหลดไฟล์ทดสอบขนาดที่กำหนดออกจาก cloud | ค่า data transfer | ต่ำถึงปานกลาง ขึ้นกับขนาดไฟล์ |

แนะนำให้เริ่มจาก TC-A เพราะควบคุมง่าย ย้อนกลับได้ทันที และ compute เป็นค่าใช้จ่ายหลักของทั้งสองฝั่งอยู่แล้ว

ก่อนทดลองทุกครั้งต้องผ่านเช็คลิสต์นี้ เพราะเราตั้งใจทำให้เกิดค่าใช้จ่ายจริง

1. Budget Alert ของ AWS และ GCP (ตั้งไว้ที่ 1 USD) ยังทำงานอยู่
2. กำหนดเวลาสิ้นสุดการทดลองไว้ล่วงหน้าแน่นอน
3. ตั้งเตือนในนาฬิกาหรือปฏิทินให้กลับมา revert
4. ทดลองในช่วงที่เฝ้าดูได้ต่อเนื่อง
5. จดชื่อ instance และ resource ID ที่ใช้ทดลองไว้ ป้องกันแก้ผิดตัว

ขั้นตอนทั่วไป

1. บันทึก baseline ค่าใช้จ่ายของ `AWS-Cost-Monitor` และ `GCP-Cost-Monitor` ใน Grafana (screenshot พร้อมเวลา)
2. จดเวลาปัจจุบันแม่นยำเป็นจุดเริ่ม
3. ทำการกระทำบน AWS ก่อน แล้วทำบน GCP ตามทันที (ห่างกันไม่เกิน 1 ถึง 2 นาที) จดเวลาแต่ละฝั่งแยกกัน
4. ปล่อยให้คงอยู่ตามระยะเวลาของ test case นั้น
5. ระหว่างรอ เข้าดู Grafana เป็นระยะ จดเวลาที่ค่าใช้จ่ายเริ่มขยับครั้งแรกของแต่ละ cloud ค่านี้คือ detection latency
6. ครบเวลาแล้ว revert ทั้งสองฝั่ง จดเวลาที่เสร็จ
7. จดค่าใช้จ่ายสุดท้ายที่เห็น แล้วกรอกทั้งหมดลง `cost_test_case_results.xlsx`
8. Screenshot กราฟที่เห็นค่าใช้จ่ายพุ่งขึ้นแล้วลงเก็บเป็นหลักฐาน

แผน rollback ของแต่ละแบบ: TC-A หยุด instance แล้วเปลี่ยนชนิดกลับเป็นขนาดเดิมแล้ว start ใหม่, TC-B detach แล้วลบดิสก์ที่เพิ่ม, TC-C ลบไฟล์ทดสอบที่ค้างอยู่ใน bucket

สถานะ ณ ตอนที่เขียนคู่มือนี้: เอกสารและตารางพร้อมใช้ แต่ยังไม่ได้ลงมือทดลองจริง ตาราง Test Log จึงยังไม่มีผล

ข้อควรรู้เรื่องค่าใช้จ่ายที่ใช้คิดตัวแปรของการทดลอง สิ่งที่ทำให้ค่าใช้จ่ายของทั้งสอง cloud เพิ่มขึ้นหลักๆ คือ ขนาดและชั่วโมงใช้งานของ instance, ขนาดและชนิดของดิสก์ รวมถึงระยะเวลาที่เก็บไว้, ข้อมูลที่ออกจาก cloud, ทรัพยากรที่ลืมปิดอย่าง public IP และ snapshot, และสำหรับ t3 ของ AWS คือ surplus credit เมื่อโหมด Unlimited เปิดอยู่และใช้ CPU สูงต่อเนื่อง ส่วนความเร็วที่เห็นตัวเลข AWS Cost Explorer ตามหลังความจริงประมาณ 24 ชั่วโมง ขณะที่ GCP ต้องรอข้อมูลลง BigQuery และสคริปต์ของเราดึงข้อมูลวันละครั้ง จึงไม่ควรคาดว่าจะเห็นการเปลี่ยนแปลงภายในไม่กี่นาที

---

## 13. ปัญหาที่เจอและวิธีแก้

เรียงตามลำดับของคู่มือ ทุกข้อเกิดขึ้นจริงตอนทำโปรเจกต์นี้

### ZBX สีแดง หรือ "Connection refused" ที่ port 10050

เช็คตามลำดับ (1) บนเครื่องนั้น `sudo systemctl status zabbix-agent2` ว่ารันอยู่ไหม (2) ค่า `Hostname=` ใน `zabbix_agent2.conf` ต้องตรงกับ Host name ในหน้าเว็บทุกตัวอักษร (3) ค่า `Server=` ต้องเป็น IP ของฝ่ายที่มาถาม คือ Zabbix Server สำหรับ on-prem หรือ IP ภายในของ proxy สำหรับ AWS/GCP (4) Security Group หรือ Firewall ต้องเปิด 10050 ให้ฝ่ายที่มาถาม (5) IP ใน Interface ของ host ในหน้าเว็บถูกต้อง ดู log ได้ที่ `/var/log/zabbix/zabbix_agent2.log`

### Proxy เป็นสีแดง Last seen เป็น Never และ nc ไป 172.16.46.104:10051 ไม่ผ่าน

ตั้ง proxy เป็น Active ไว้ ซึ่งไม่มีทางใช้ได้เมื่อ Zabbix Server อยู่หลัง NAT เปลี่ยนเป็น Passive: ใน `zabbix_proxy.conf` ตั้ง `ProxyMode=1` แล้วลบ proxy เดิมในหน้าเว็บ สร้างใหม่ในโหมด Passive ด้วย Public IP ของ proxy (ตอนแก้ เรากดสร้างซ้ำจนได้ proxy ซ้ำ ให้ลบอันที่ซ้ำออก) แล้วรีสตาร์ท `sudo systemctl restart zabbix-proxy` และเช็คว่า Security Group ของ proxy เปิด 10050-10051 จาก `<ON_PREM_PUBLIC_IP>/32`

### log ของ proxy: "connection from ... rejected, allowed hosts: ..."

ค่า `Server=` ใน proxy ที่เป็น Passive ต้องเป็น Public IP ของเครือข่ายที่ Zabbix Server อยู่ ไม่ใช่ IP ภายในของ server

### `proxy.sql.gz` หาไม่เจอ

Zabbix 7.0.28 แจกไฟล์ `proxy.sql` ไม่บีบอัด สั่ง `ls /usr/share/zabbix-sql-scripts/sqlite3/` ดูชื่อไฟล์จริงก่อน แล้วใช้ `sqlite3 ... < proxy.sql`

### proxy log: "unable to open database file"

ยังไม่ได้สร้าง `/var/lib/zabbix` หรือไม่ใช่ของ user `zabbix` ทำ `sudo mkdir -p /var/lib/zabbix && sudo chown zabbix:zabbix /var/lib/zabbix` แล้วนำเข้า schema ใหม่

### `Permission denied` ตอน `ls` หรือ `cat` ไฟล์ของ zabbix

ปกติของการตั้ง `chmod 750` หรือ `600` ใช้ `sudo` นำหน้า

### `zabbix_get: command not found` หรือ `zabbix_get` ไป target แล้ว timeout

ไม่พบคำสั่ง: ติดตั้ง `zabbix-get` หลังเพิ่ม repo ของ Zabbix 7.0 แล้ว (ถ้าติดตั้งก่อน Ubuntu จะเสนอแพ็กเกจ 6.0 มาให้) ส่วน timeout: Security Group หรือ Firewall ของ target ไม่ได้เปิด 10050 ให้ IP ภายในของ proxy ยืนยัน IP นั้นด้วย `hostname -I` บน proxy อย่าเดา

### SSH เข้า EC2 หรือ VM แล้วค้างไม่ตอบ

IP ของเครือข่ายเราเปลี่ยน (ผู้ให้บริการอินเทอร์เน็ตให้ IP แบบ dynamic) กฎ SSH ที่จำกัดเฉพาะ "My IP" จึงไม่ตรงอีกแล้ว เข้าไปแก้ source ของกฎให้เป็น IP ปัจจุบัน และถ้าเป็น EC2 ที่ Stop/Start มา Public IP ของเครื่องก็เปลี่ยนด้วย

### Discovery action: "No operations defined"

Action ต้องมี Operations อย่างน้อยหนึ่งรายการ (Add host, Add to host groups, Link to templates) ใส่แค่ Conditions ไม่พอ

### host ที่ discovery เพิ่มเข้ามาชื่อเป็นเลข IP

ที่ discovery rule ตั้ง Device uniqueness criteria และ Host name เป็น `Zabbix agent "agent.hostname"` และต้องเพิ่มเช็ค `agent.hostname` ในรายการ Checks ก่อน ถึงจะเลือกได้

### ลบ host ที่ discovery เพิ่มแล้วรอเท่าไรก็ไม่กลับมา

ดูข้อควรรู้ท้ายข้อ 5.8 ต้องหยุด agent บนเครื่องนั้นให้ Discovery เห็นเป็น Down ก่อน แล้ว start ใหม่

### route table ของ VPC ผิดตัว / ฟอร์ม Launch instance รีเซ็ตเอง

route table: ดูคอลัมน์ VPC ทุกครั้ง อย่าแก้ตัวของ Default VPC ฟอร์ม Launch instance: พอเปลี่ยน AMI, instance type, key pair และ security group อาจถูกรีเซ็ต ตรวจทุกช่องก่อนกด Launch

### Grafana: "Could not connect to given url" หรือ HTTP 412

URL ของ data source ต้องเป็น `http://<server>/zabbix/api_jsonrpc.php` มี `/zabbix/` และเข้าถึงได้จากเครื่อง Grafana

### Grafana: "No permissions to call hostgroup.get"

ผู้ใช้ API เป็น Guest role ซึ่งปิดการเรียก API ทั้งหมด สร้างผู้ใช้ใหม่หรือแก้ Role เป็น `User role` แล้วออก API token ใหม่

### Grafana: "No data" ทั้งที่ Zabbix มีข้อมูล

ดูข้อ 8.6 ท้ายส่วน คือ History storage period ของ item, Host permissions ที่ User group (ไม่ใช่ที่ตัว user) และช่วงเวลาที่เลือก

### Import dashboard ไม่ผ่าน

ข้อความ `DashboardSpec.timeSettings.weekStart: Invalid value: conflicting values` เกิดจากมี `"weekStart": ""` ใน JSON ให้ลบคีย์ `weekStart` ออกทั้งบรรทัด ไม่ใช่ตั้งเป็นค่าว่าง ถ้า error อ้างถึง `apiVersion` ให้ใช้ `dashboard.grafana.app/v2` และถ้าแก้ไฟล์เอง ควรมี annotation แบบ default ครบ ไฟล์ใน repo นี้แก้ให้ผ่านแล้ว

### Panel Network ว่าง หรือ panel อ้าง data source ไม่เจอ

ชื่อ interface ไม่ตรง (ดู `ip -br a` แล้วแก้ชื่อ item ใน panel) หรือยังไม่ได้แทนที่ uid ของ data source ในไฟล์ JSON ตามข้อ 8.5

### `zabbix_sender` ตอบ `processed: 0; failed: N`

host, item หรือ discovery rule ใน Zabbix ยังไม่มีหรือชื่อ/key ไม่ตรงกับที่สคริปต์ส่ง ตรวจตามตารางในข้อ 7.1 ทีละช่อง และสำหรับ item แยกตามบริการ ให้ส่งซ้ำอีกครั้งหลัง discovery สร้าง item เสร็จ

### สคริปต์ GCP รันจบ ไม่ error แต่ไฟล์ log ว่าง

ไลบรารี `google-cloud-bigquery` ตั้งค่า logging ของ Python ไว้ก่อนตอน import ทำให้ `logging.basicConfig()` ใน script ไม่มีผล แก้ด้วย `force=True` (สคริปต์ใน repo นี้แก้แล้ว)

### สร้าง JSON key ของ service account ไม่ได้

Organization Policy บล็อกอยู่ ไม่ต้องสร้าง ผูก service account เข้ากับ VM แทน ตามข้อ 6.2 และ 6.4

### GCP: 403 หรือ Permission denied ตอนเรียก BigQuery

service account อยู่คนละโปรเจกต์กับ dataset ให้สิทธิ์ BigQuery Data Viewer และ BigQuery Job User ที่โปรเจกต์ของ dataset โดยตรง ไม่ต้องสร้างของใหม่

### GCP: ปุ่ม SSH ใน Console ขึ้น "Connection via Cloud Identity-Aware Proxy Failed"

เพิ่ม firewall rule ให้ช่อง `35.235.240.0/20` เข้า tcp:22 ของ VM (tag ของ VM กับ tag ในกฎต้องตรงกัน)

### GCP: ค่าใช้จ่ายสูงผิดปกติ

ดูหมายเหตุท้ายข้อ 7.3 ตรวจด้วยว่า VM ตัวที่สอง ดิสก์ชนิด Balanced หรือ region นอกเหนือ Always Free ทำให้ถูกคิดเงินหรือเปล่า

### digest ได้ HTTP 404

`ZABBIX_URL` ในสคริปต์ขาด `/zabbix/` ต้องเป็น `http://<server>/zabbix/api_jsonrpc.php`

### LINE: หาตัวเลือก Messaging API ไม่เจอ

ต้องสร้าง Official Account ที่ manager.line.biz ก่อนแล้วเปิด Messaging API จากที่นั่น ตามข้อ 9.1 ทดสอบ Media type ผ่านแต่ข้อความจริงไม่มา: ยังไม่ได้เพิ่มบอทเป็นเพื่อน หรือโควตาข้อความต่อเดือนของแผนหมด

### Flask: `ModuleNotFoundError: No module named 'flask'` ใน `flask.log`

ติดตั้ง flask กับ user ที่รันแอป (`pip3 install flask`, บน Ubuntu 24.04 ต้องเติม `--break-system-packages`) แล้วรันใหม่

### JMeter ยิงแล้ว CPU ไม่ถึง 100% / กราฟค่าใช้จ่ายไม่ขยับ

ทั้งสองอย่างเป็นพฤติกรรมปกติ ดูข้อ 11.3

---

## 14. เรื่องความลับและการปิดเครื่องหลังใช้งาน

ความลับ

- ใน repo นี้ไม่มี token, PSK, password หรือ access key จริง ทุกจุดเป็น placeholder ใส่ค่าจริงบนเครื่องปลายทางโดยตรง อย่า commit กลับขึ้น Git ไฟล์ `.gitignore` กันไฟล์ `.env`, `*.pem`, `credentials` และ `*.jtl` ไว้ให้แล้ว
- ถ้าเผลอพิมพ์ PSK หรือ token ลงแชท เอกสาร หรือ commit ไปแล้ว ให้ถือว่ารั่ว: สร้าง PSK ใหม่ (`openssl rand -hex 32`) แก้ไฟล์บน proxy และในหน้าเว็บ Zabbix, ออก LINE Channel access token ใหม่ที่ LINE Developers Console, ลบแล้วสร้าง Zabbix API token และ AWS access key ใหม่
- ก่อนเปิด repo เป็นสาธารณะ ค้นหา IP ที่เป็นของจริงของคุณ (Public IP ของเครือข่าย, IP ของ instance) และ Project ID กับชื่อตาราง billing ของ GCP ในทุกไฟล์ แล้วเปลี่ยนเป็น placeholder

ปิดเครื่องเมื่อไม่ใช้

- AWS: Stop `zabbix-proxy-aws`, `ec2-target-01` และเครื่องอื่นที่เปิดไว้ (Stop ไม่คิดค่า compute แต่ EBS volume ยังคิดอยู่) ถ้าเลิกใช้จริงให้ Terminate และลบ volume, Elastic IP ที่ไม่ได้ใช้
- GCP: Stop VM ทั้งสองเครื่อง (ดิสก์ยังคิดอยู่ตามขนาด) ถ้าเลิกใช้ให้ Delete
- ลบกฎ port 5000 ใน Security Group และ Firewall
- Budget Alert ปล่อยเปิดไว้ต่อ
- ถ้าปิด Zabbix Server หรือ proxy ไปนาน cron ของ aggregator จะหยุด digest จะอ่านค่าเก่าและส่งยอดวันเดิมซ้ำ ตรวจบรรทัด "ข้อมูลล่าสุด" ท้ายข้อความ

---

## 15. ไฟล์ใน repo นี้

```
README.md                    คู่มือนี้
scripts/
  aws_cost_aggregator.py     ดึงค่าใช้จ่ายจาก Cost Explorer ส่งเข้า Zabbix (รันบน proxy ฝั่ง AWS)
  gcp_cost_aggregator.py     ดึงค่าใช้จ่ายจาก BigQuery billing export ส่งเข้า Zabbix (รันบน proxy ฝั่ง GCP)
  daily_cost_digest.py       สรุปค่าใช้จ่ายสองฝั่งส่งเข้า LINE (รันบน Zabbix Server)
  cpu_load_app.py            แอป Flask เผา CPU สำหรับ JMeter
grafana/
  Hybrid_Cloud_Executive_Overview.json
  Hybrid_Cloud_Cost_and_Performance_Dashboard.json
  ec2-target-01.json
  gcp-target-01.json
  Zabbix_Agent_On_Prem.json
load-testing/
  hybrid_cloud_load_test.jmx            แผนสำหรับเดโม
  hybrid_cloud_loadtest_scenarios.jmx   แผนสำหรับ test case LT-01 ถึง LT-08
  load_test_cases.xlsx                  ตารางออกแบบและบันทึกผล test case
config/
  zabbix_config_reference.md  ไฟล์ .conf ทุกเครื่องรวมไว้ที่เดียว
planning-docs/               เอกสารวางแผนโครงงาน
  1.1_System_Architecture_Document (pdf)
  1.2_Technology_Stack_Justification (pdf)
  1.3_Network_Design_Document (pdf)
  1.4_Project_Plan_Gantt.xlsx
  1.4_Project_Plan_RiskRegister.docx
  Cost_Test_Case_Protocol.docx
  cost_test_case_results.xlsx
```

เวอร์ชันที่ใช้: Zabbix 7.0.28, MariaDB, Apache, Grafana 13 พร้อมปลั๊กอิน `alexanderzobnin-zabbix-app`, Ubuntu 22.04 (on-prem) และ 24.04 (AWS, GCP), Python 3, boto3, google-cloud-bigquery, Flask, Apache JMeter

โครงงานนี้ทำเพื่อการศึกษา นำไปใช้ต่อได้ตามสะดวก ไม่มีการรับประกันใดๆ ทำและเขียนโดยนักศึกษา ไม่ใช่งานของผู้ผลิตซอฟต์แวร์
