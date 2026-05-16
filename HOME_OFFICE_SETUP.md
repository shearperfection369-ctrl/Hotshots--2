# Orisei TMS · Home-Office Self-Hosting Plan

**Goal:** stand up the full Orisei Freight Solutions TMS (React + FastAPI + MongoDB) in your home office, end-to-end independent from any cloud platform, with production-grade uptime, security, and recovery.

**Scope:** every piece of hardware, every cable, every step of installation, every security hardening, and the exact day-by-day execution plan to get from "empty desk" to "live brokerage running on my own iron" in **about 14 days**.

**Currency:** USD · **Year:** 2026 · **Last updated:** 2026-02-14

---

## 0 · TL;DR

| Tier | Hardware budget | Use case | Uptime target |
| --- | ---: | --- | ---: |
| **Lab / Solo founder** | **~$1,800** | One operator, no SLA · 1 box · 100/100 Mbps fiber | 99.0% |
| **Recommended Production** | **~$4,200** | 1–5 seats · Oliver + agent + ops · failover-ready | 99.5% |
| **HA / Brokerage-scale** | **~$8,500** | 5–10 seats · paying customers depending on it | 99.9%+ |

**Time to first request served:** ~3 hours after the gear arrives at your desk.
**Time to production-grade with backups, TLS, monitoring, and security hardening:** **10–14 days**.

> Reality check first: read §1 before buying anything. For most freight brokerages running a single instance, **a $90/mo cloud deployment outperforms a $4,200 home rack in every dimension that actually matters** (uptime, security, latency, ops burden). The home rack wins on **control, learning, recurring cost at scale, and air-gap resilience** — make sure you want those.

---

## 1 · When does home hosting actually make sense?

### Choose home hosting if:
- You want **complete data sovereignty** (no Atlas, no Vercel, no Cloudflare touching your customer freight data).
- You enjoy hands-on infra and want a real lab.
- You'll keep more than ~10 tenants on the platform and the cloud SaaS bill exceeds **$1,000/mo** (the crossover point).
- You're in a metro with **business-class symmetric fiber** (≥ 250/250 Mbps with static IPv4).
- You can tolerate a **rare planned outage** (firmware updates, ISP cuts, MN ice storms).

### Stay in the cloud if:
- You're running **Tier A solo or Tier B small brokerage** (see `COST_ANALYSIS.md`) — the cloud bill is < $4K/yr and cloud SLAs are better than anything you can do alone.
- A 4-hour outage in February costs you a **major shipper account**.
- You don't have a second person who can physically reach the rack if you're traveling.
- Your house has **single-circuit power** with no UPS-room.

If you proceed anyway, the rest of this document is your build manual.

---

## 2 · Architecture you're recreating

The Orisei TMS is **three movable parts**:

| Layer | What it is | How we'll run it at home |
| --- | --- | --- |
| **Frontend** | React 19 static bundle (~5 MB) | Served by `caddy` from `/srv/orisei/frontend/build` |
| **Backend** | FastAPI · Python 3.11 · uvicorn | `systemd` unit running on `127.0.0.1:8001` |
| **Database** | MongoDB 7.x replica set | `systemd` unit running on `127.0.0.1:27017` |
| **Reverse proxy + TLS** | Caddy (auto-HTTPS via Let's Encrypt) | `systemd`-managed Caddy fronts both layers |
| **Edge / DNS** | Cloudflare (proxy + WAF + caching) | Free tier covers everything |
| **Backups** | `mongodump` + `restic` to off-site object storage | Cron + Backblaze B2 (cheapest object storage that works) |
| **Monitoring** | UptimeRobot (external) + Netdata (local) | Free tier UptimeRobot, Netdata free agent |

**You do NOT self-host:**
- Emergent-managed Google Auth → keep using `auth.emergentagent.com` (no reason to re-implement)
- Emergent LLM gateway → keep using the Universal Key
- DAT / Truckstop / RMIS / QuickBooks / Stripe / Resend / factoring partners → external SaaS by design
- TLS certificate management → Let's Encrypt does it via Caddy

---

## 3 · Hardware Bill of Materials

### 3.1 · Tier "Lab" (~$1,800) — single box, no failover

| Item | Spec | Notes | Price |
| --- | --- | --- | ---: |
| **Server** | Beelink SER8 or Minisforum UM790 Pro Mini PC · AMD Ryzen 7 8845HS · **32 GB DDR5** · **1 TB NVMe SSD** | Same physical footprint as a paperback; runs whisper-quiet | $799 |
| **UPS** | APC Back-UPS BR1500MS2 · 1500 VA · pure sine-wave · USB management | Holds the server + router for ~25 min during outages | $230 |
| **Router** | UniFi Cloud Gateway Ultra or pfSense Netgate 2100 | Real firewall, real VLANs | $199 |
| **Switch** | UniFi Switch Lite 8 PoE | 8 ports, 4× PoE for cameras/APs | $109 |
| **Wired backup line** | Verizon LTE failover modem (one-time) | Auto-switch when your fiber dies | $89 |
| **Cabling + rack-mount shelf** | Cat 6 + 6U wall rack + IEC cords | Keeps it neat | $120 |
| **Status display** | 7" HDMI touchscreen for dashboards | Optional but motivating | $85 |
| **Surge protector + power strip** | Tripp Lite 12-outlet | Behind the UPS | $40 |
| **External backup drive** | 4 TB USB-C SSD (Samsung T7 Shield) | First-stage local backup | $260 |
| **Subtotal — Lab tier** | | | **~$1,930** |

### 3.2 · Tier "Recommended Production" (~$4,200) — survives one failure

Adds redundancy. The single biggest improvement vs Lab: **a hot standby box**.

| Item | Spec | Notes | Price |
| --- | --- | --- | ---: |
| **Primary server** | Beelink SER8 (8845HS · 32 GB · 1 TB NVMe) | App + DB primary | $799 |
| **Standby server** | Identical Beelink SER8 | MongoDB secondary + frontend hot-standby | $799 |
| **NAS** | Synology DS224+ + 2× 4 TB Seagate IronWolf (RAID 1) | Local backup target | $620 |
| **UPS** | CyberPower CP1500PFCLCD pure sine-wave (1500 VA) ×1 | + smaller 600 VA for the NAS | $260 |
| **Router + Switch** | UniFi Cloud Gateway Max + UniFi Switch 8 PoE-150W | Network segmentation by VLAN | $548 |
| **LTE failover** | Cradlepoint or UniFi LTE Pro · with a T-Mobile data plan | Auto-fail fiber → LTE in <10s | $349 + ~$25/mo |
| **Status display** | 15.6" portable USB-C monitor mounted in rack | Netdata + Grafana dashboards | $189 |
| **Rack** | StarTech 12U open-frame rack on casters | Easy access | $189 |
| **Patch panel + cabling** | Cat6A + keystone jacks + management | Clean install | $180 |
| **Smart PDU** | Tripp Lite metered PDU | Remote power-cycle ports | $260 |
| **Subtotal — Production tier** | | | **~$4,193** |

### 3.3 · Tier "HA" (~$8,500) — small fleet of customers depends on it

Adds **true redundancy** (no single point of failure) + secondary site.

| Item | Spec | Notes | Price |
| --- | --- | --- | ---: |
| 3× Compute nodes | Beelink SER8 ×3 OR a single Dell R650 1U | 3-node MongoDB replica set + 2× app nodes | $2,400 |
| 4-bay NAS | Synology DS424+ with 4× 8 TB IronWolf (SHR-2) | 24 TB usable, dual-disk fail tolerance | $1,400 |
| 2× UPS | Eaton 5PX 1500 with extended battery + network mgmt | True 60-min runtime | $1,400 |
| Real firewall | UniFi Dream Machine Pro Max OR pfSense Netgate 4200 | Threat detection, IDS/IPS, deep packet | $599 |
| 24-port managed switch | UniFi Switch Pro 24 PoE | VLANs, link aggregation | $799 |
| Off-site colo cabinet | 1U at a regional facility (e.g., MNDC.io in St. Paul) | Disaster recovery target | $99/mo |
| Out-of-band management | Raritan Dominion KVM IP module | Recover even if SSH dies | $499 |
| Tape archive (quarterly) | LTO-9 external + 5 tapes for cold offsite | Optional, but cheap insurance | $1,200 |
| **Subtotal — HA tier** | | | **~$8,797** |

---

## 4 · Network Requirements

### 4.1 · Internet service

| Property | Minimum (Lab) | Recommended (Production) | HA |
| --- | --- | --- | --- |
| Plan type | Residential fiber | **Business fiber** (required for static IP + SLA) | Business fiber + LTE failover |
| Down/Up | 250/250 Mbps | 1 Gbps / 1 Gbps | 2 Gbps + bonded LTE |
| Static IPv4 | optional | **required** | required, plus a /29 subnet |
| Provider examples (Twin Cities) | USI Fiber, CenturyLink Fiber | Comcast Business, Lumen Business, US Internet | Bandwidth.com, Lumen, dedicated colo cross-connect |
| Monthly cost | ~$90 | ~$150–250 | ~$400 |

### 4.2 · Domain + DNS

- Buy `oriseifreight.com` (or your domain) at **Cloudflare Registrar** ($10/yr — cheapest, no markup).
- Cloudflare nameservers handle DNS, DDoS, caching, WAF.
- Create A record `app.oriseifreight.com` → your static public IP.
- Set Cloudflare proxy "On" — hides your home IP from the internet.

### 4.3 · Inbound firewall rules (UniFi / pfSense)

```
ALLOW  Cloudflare-IPs   → wan_ip:443     (TCP)   # HTTPS only, only Cloudflare can hit it
ALLOW  your_office_ip   → wan_ip:22      (TCP)   # SSH (or use Tailscale instead — preferred)
DENY   any              → any                     # default deny
```

Lock down SSH to a **Tailscale tailnet** instead of opening 22 to the world — your laptop joins the tailnet, the server joins the tailnet, no public SSH port at all.

---

## 5 · Software Stack

| Component | Version | Why |
| --- | --- | --- |
| **OS** | Ubuntu Server 24.04 LTS | 5 years of security updates, well-documented |
| **Container runtime** | Docker 26 + Compose v2 | Optional — only used for MongoDB replica set if you prefer containers |
| **Database** | MongoDB 7.x Community Server | Same engine the app is already using |
| **Python** | 3.11.x via `uv` or system pyenv | Backend runtime |
| **Node** | 20 LTS | For frontend build only |
| **Reverse proxy** | Caddy 2.x | Auto-HTTPS, simpler than nginx |
| **Process manager** | systemd | Native, no extra moving parts |
| **Backups** | `mongodump` + `restic` 0.18 | Encrypted off-site backups |
| **Monitoring** | Netdata + UptimeRobot + Grafana (optional) | Free tiers cover everything |
| **Edge security** | Cloudflare Pro tier ($20/mo) | WAF + rate limit + advanced DDoS |
| **VPN / SSH** | Tailscale free plan | No exposed SSH port |
| **Email outbound** | Resend OR Mailgun | $0–20/mo, much easier than postfix |

---

## 6 · Day-by-Day Execution Plan (14 days)

### Day 1 · Procurement & site prep
- Order all hardware from §3 (Amazon Business, Newegg, ipchaa.com, Synology direct, ui.com).
- Tell ISP you need **business class fiber with a static IP**; install ETA 5–10 business days. Schedule it.
- Identify the room: dry, 60–75°F ambient, single dedicated 15-amp circuit, good signal to Wi-Fi (or hard-wired desk).

### Day 2 · Domain + Cloudflare
- Buy `oriseifreight.com` at Cloudflare Registrar.
- Add to Cloudflare account, switch to Cloudflare nameservers.
- Create `app.oriseifreight.com` A record (placeholder 1.1.1.1 for now, with proxy ON).

### Day 3 · ISP install
- ISP installs fiber + ONT. Confirm your **static public IPv4** in writing.
- Test from a phone tethered through the ONT before plugging in your gear.

### Day 4 · Rack the gear
- Stand up the rack/shelf, mount UPS, switch, router, server.
- Cable management: every Cat6 labeled at both ends.
- Plug UPS into wall (NEVER into a surge strip — UPS goes upstream of strips).
- Plug router + switch + server into UPS-protected outlets.
- Power on. Verify router gets WAN address.

### Day 5 · OS install & hardening
- Boot Ubuntu 24.04 LTS from USB.
- Static IP for the server inside your LAN (e.g., 10.0.10.10).
- Create non-root user `orisei` · disable root SSH · key-only SSH · UFW deny everything except 22 on your LAN.
- Install Tailscale, join your tailnet. **Now close port 22 to the WAN entirely.**
- `unattended-upgrades` on. `fail2ban` installed. `auditd` for forensics.

### Day 6 · MongoDB
- Add the official MongoDB 7 apt repo.
- Install `mongodb-org`, enable + start, bind only to `127.0.0.1`.
- Configure as a **single-node replica set** (`rs.initiate()`) — needed for change-streams + atomic transactions, both used by the app.
- Create admin + app users, set `--auth`. Save creds in your password manager.
- Test from `mongosh` localhost only.

### Day 7 · App deployment — backend
- Install Python 3.11, create `/srv/orisei`, clone the repo (or rsync your latest build), set up a venv.
- Copy `/app/backend/.env` from preview — but **only the keys that are home-environment specific**: `MONGO_URL=mongodb://orisei_app:****@127.0.0.1:27017/orisei`, `DB_NAME=orisei`.
- Keep the Emergent LLM Key as-is — it works anywhere.
- Set `CONNECTIONS_ENCRYPTION_KEY` (generate fresh on first boot — Fernet helper does this automatically).
- `pip install -r requirements.txt`.
- Create `/etc/systemd/system/orisei-backend.service`:
  ```
  [Unit]
  Description=Orisei FastAPI backend
  After=network.target mongod.service
  [Service]
  User=orisei
  WorkingDirectory=/srv/orisei/backend
  ExecStart=/srv/orisei/.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
  Restart=always
  RestartSec=2
  [Install]
  WantedBy=multi-user.target
  ```
- `systemctl enable --now orisei-backend`.
- Smoke-test: `curl http://127.0.0.1:8001/api/health`.

### Day 8 · App deployment — frontend
- Install Node 20, run `yarn install && yarn build` on `/app/frontend`.
- Copy the resulting `build/` to `/srv/orisei/frontend/build`.
- **CRITICAL:** before building, set `REACT_APP_BACKEND_URL=https://app.oriseifreight.com` so the bundle calls your own host, not Emergent's preview.
- `yarn build` is now cached; next deploy is a single rsync.

### Day 9 · Caddy + TLS
- Install Caddy via the official apt repo.
- `/etc/caddy/Caddyfile`:
  ```
  app.oriseifreight.com {
    encode gzip
    root * /srv/orisei/frontend/build
    handle /api/* {
      reverse_proxy 127.0.0.1:8001
    }
    handle {
      try_files {path} /index.html
      file_server
    }
  }
  ```
- Turn Cloudflare proxy OFF for 5 minutes while Caddy negotiates Let's Encrypt cert. Then turn proxy back ON.
- Hit `https://app.oriseifreight.com` from your phone over LTE — log in flow should work end-to-end.

### Day 10 · Backups
- Install `restic` and `mongodb-database-tools`.
- Create a Backblaze B2 bucket (`orisei-backups`).
- Cron job at 02:00 daily:
  ```
  mongodump --uri $MONGO_URL --gzip --archive=/tmp/orisei.gz \
    && restic backup /tmp/orisei.gz /srv/orisei/uploads \
    && rm /tmp/orisei.gz
  ```
- Configure `restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 12 --prune`.
- Test the restore path **today** by restoring to a scratch directory and counting records. Never trust an untested backup.

### Day 11 · Monitoring
- Install Netdata agent → connects to free Netdata Cloud → dashboard from any browser.
- UptimeRobot: add monitor for `https://app.oriseifreight.com` every 60s. Slack/email alert on 2+ consecutive failures.
- Wire your phone number into the UptimeRobot voice-call escalation.
- Add a `/api/health` endpoint check that also pings Mongo — alarms on DB outages, not just web outages.

### Day 12 · Edge hardening (Cloudflare)
- Cloudflare Rules:
  - Rate-limit `/api/auth/*` to **20 requests / 10 minutes / IP**.
  - Geo-block countries you don't ship to (drops 80% of bot traffic).
  - WAF managed rules ON: OWASP, Cloudflare Specials.
  - Bot Fight Mode ON.
- Cloudflare Access (free tier) → require login on `/admin/*` paths for an extra layer.
- TLS minimum version 1.2 (default).

### Day 13 · Game-day rehearsal
Simulate three failures, fix each, document the runbook:

1. **Power cut**: pull the wall plug. Server stays up on UPS. Confirm graceful shutdown if outage > 15 min.
2. **ISP cut**: unplug the fiber WAN. LTE failover triggers in <30s. Test that the public DNS still points at you (it does — your static IP isn't on LTE; Cloudflare proxy buffers the gap).
3. **DB corruption**: stop Mongo, rename `/var/lib/mongodb/`, restore from Backblaze, restart. Document the elapsed time (target: < 30 min for last 24h restore).

### Day 14 · Cut-over plan
- Two-week shadow: keep the cloud preview environment running AND your home server. Compare logs nightly.
- Once you're confident, set Cloudflare DNS to point at home, sunset the cloud deployment, archive its data, save $X/mo.

---

## 7 · Recurring operating cost (vs cloud baseline)

| Line item | Home-office monthly | Cloud Tier A monthly (from COST_ANALYSIS.md) |
| --- | ---: | ---: |
| Internet (business fiber + static IP) | $180 | $0 (built into platform fee) |
| Electricity (40W average × 24/7) | $4 | $0 |
| Cloudflare Pro | $20 | $0 (free tier OK) |
| Backblaze B2 (~25 GB) | $0.50 | $0 |
| UptimeRobot free / Netdata free | $0 | $0 |
| Tailscale free | $0 | $0 |
| LTE failover data plan | $25 | $0 |
| Hardware amortized (3 yr / $4,200) | $116 | $90 (app hosting + Atlas) |
| **Total recurring** | **~$345 / mo** | **~$115 / mo** |

> Bottom line: home hosting is **~$230/mo more expensive** through Tier A. It only crosses over once cloud spend exceeds **~$1,000/mo**, which happens at **>10 tenants** in this app's economic model. Build the rack for control or learning, not to save money.

---

## 8 · Security hardening checklist (must-do)

- [ ] All services bind only to `127.0.0.1`. Caddy is the **only** thing that listens on the public interface.
- [ ] SSH is **only reachable over the Tailscale tailnet** — port 22 is firewalled off the WAN.
- [ ] No password SSH. Keys only. `PermitRootLogin no`.
- [ ] `fail2ban` enabled with email alerts.
- [ ] `unattended-upgrades` daily, with reboot at 03:30 every Sunday.
- [ ] MongoDB has a **non-empty admin password** and `--auth`.
- [ ] Backups are **encrypted with restic** before they leave the box.
- [ ] Backblaze B2 access keys are stored in 1Password, NOT in any source-controlled file.
- [ ] CONNECTIONS_ENCRYPTION_KEY is **never committed**. Lives only in `/etc/orisei/secrets.env` mode 600.
- [ ] Cloudflare API token in 1Password.
- [ ] An external person (your CPA, attorney, or spouse) has a **sealed envelope** containing the 1Password emergency kit so a bus-factor recovery is possible.
- [ ] Quarterly **disaster-recovery drill** documented in `/srv/orisei/runbook.md`.

---

## 9 · Failure modes and how to handle them

| What broke | Symptom | What to do |
| --- | --- | --- |
| Power cut at home | App goes dark | UPS holds; if >15min, graceful shutdown auto-fires |
| ISP fiber cut | DNS still resolves but TCP times out | LTE failover takes over in <30s |
| MongoDB OOM | 500s on every API call | `systemctl restart mongod`; check `/var/log/mongodb/mongod.log`; verify `--wiredTigerCacheSizeGB` not set too high |
| Caddy out of certs | 526 from Cloudflare | Disable CF proxy → Caddy renews → re-enable |
| Disk full | Mongo writes start failing | Cron a `df -h` alert at 80% full; rotate old logs |
| You're on vacation, server dies | Total outage | This is what HA tier solves. Lab/Production tier accepts the risk. |
| Cloudflare account compromise | Domain hijacked | TFA on CF account; recovery codes in 1Password; CF has a 24h recovery window |
| Burglary | Hardware gone | Backups are off-site (B2); restore to fresh hardware in 1–2 days |
| House fire | Hardware + backups gone | Off-site colo cabinet (HA tier only) holds a hot copy |

---

## 10 · When to walk away and move back to cloud

You should redeploy back to the Emergent native cloud the moment **any** of these is true:

- You miss a customer pickup because the app was down during a power outage.
- You're spending more than **4 hours/week** on infra babysitting (it should be < 1 hour/week steady-state).
- A customer audit asks for **SOC 2** or **HIPAA** — neither is realistic for a home rack.
- You hire a 6th employee — at that scale, opex on managed cloud beats your time-to-fix-everything.
- Your power utility starts charging time-of-use rates that double your operating cost.

The cloud preview environment is intentionally kept running during your shadow period (Day 14) — keep its `/app/frontend/.env` pointed at the preview URL so you can **always cut back in under 60 seconds** by flipping Cloudflare DNS.

---

## 11 · The single-page setup checklist (print this)

```
□ Bought domain at Cloudflare Registrar
□ Hardware ordered (Beelink + UPS + UniFi + NAS)
□ Business fiber ordered with static IP
□ Ubuntu 24.04 installed
□ User created · SSH keys only · root login disabled
□ Tailscale installed and joined
□ Port 22 closed on WAN
□ UFW: allow 80,443 from CF IPs; deny everything else from WAN
□ MongoDB 7 installed · replica set initiated · auth on
□ Python 3.11 · venv · pip install requirements
□ orisei-backend.service running · curl /api/health returns 200
□ yarn build with REACT_APP_BACKEND_URL=https://app.<domain>
□ Caddy installed · TLS cert issued
□ DNS pointed at home static IP (CF proxy ON)
□ End-to-end: sign in from phone over LTE works
□ restic + B2 daily backup running · restore tested
□ UptimeRobot monitor green
□ fail2ban running · unattended-upgrades on
□ CF rate-limit + WAF + Bot Fight Mode on
□ Runbook written for: power-out, ISP-down, DB-restore
□ 1Password emergency kit handed to trusted person
```

---

## 12 · Document control

| Version | Date | Author | Note |
| --- | --- | --- | --- |
| 1.0 | 2026-02-14 | Orisei Freight Solutions LLC | Initial home-office build guide. |
