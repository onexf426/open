# LicMan — FlexLM License Manager

[English](#english) | [中文](#chinese)

开源 EDA 提效工具 — 多主机 FlexNet/FlexLM 许可证集中管理系统。

Open-source EDA productivity tool — centralized FlexNet/FlexLM license management across multiple hosts.

---

## English

### What is LicMan?

A web-based license management system for EDA (Electronic Design Automation) engineers managing FlexNet/FlexLM license servers. Manage multiple license servers across different hosts from a single browser panel — no more SSH-ing into each machine to edit license files.

### Installation

```bash
tar -xzf licman-*.tar.gz -C /opt/
cd /opt/licman
./install.sh                # default port 58080
./install.sh -port 8080     # custom port
```

The installer auto-detects the install path, patches Python shebangs and port configs, and creates data/log directories.

### Quick Start

```bash
cd /opt/licman
./bin/licman start          # start
./bin/licman stop           # stop
./bin/licman restart        # restart
./bin/licman status         # check status
```

Open browser: `http://localhost:58080`

### Features

**License Configuration Management**
- Create, edit, clone, and delete lmgrd configurations
- Start, stop (via lmdown), and reread (via lmreread) license daemons
- Interactive file browser for selecting lmgrd binary, license file, log paths
- Live command preview while editing configs

**Vendor Management**
- Manage EDA vendor daemons (Synopsys snpslmd, Cadence cdslmd, etc.)
- Define default daemon binary path per vendor (written to DAEMON line column 3)
- Define default exclude/options file per vendor (written to DAEMON line column 4)
- Host-specific vendor configurations for multi-host environments

**Real-time Usage Monitoring**
- View live feature-level license usage (total, in-use, utilization %)
- Inspect current users per feature (username, host, display, daemon version)
- Auto-refresh with configurable intervals
- Dashboard alerts when usage exceeds 85%

**Multi-Host Management**
- Add remote hosts with SSH credentials
- Transparent SSH-based file browsing, license file preview, and DAEMON line detection
- SSH ControlMaster connection multiplexing for reduced latency
- Per-host config grouping on the dashboard

**DAEMON/VENDOR Line Auto-Injection**
- Auto-detect existing DAEMON/VENDOR lines in license files
- Smart conflict detection: shows current vs. configured values for daemon path (col 3) and exclude file (col 4)
- Prompts user before overwriting existing values
- Auto-creates `.bak` backup before writing
- Also updates SERVER line hostname (line 1, col 2)

**License Expiry Alerts**
- Parses INCREMENT/FEATURE rows for expiration dates
- Shows earliest expiring feature per configuration on the dashboard
- Configurable warning threshold (default 30 days)

**Email Notifications**
- Configure SMTP; auto-send on license expiry or >90% utilization
- Test email button for verification

**Usage Trends**
- Dual view: by vendor (aggregate) or by individual feature
- Bar charts for 6h / 24h / 3d / 7d time windows
- Manual snapshot recording or cron-based automation

**Data Management**
- One-click backup: exports all configs, vendors, hosts, settings, logs as JSON
- One-click restore: merges or replaces existing data
- CSV report export for usage history
- Config cloning: duplicate a configuration with a single click

**Extras**
- Web terminal: full shell access in-browser via xterm.js + Socket.IO
- Debug log viewer with live tail (SSE)
- Operation audit log

### Cron Usage Snapshots

```bash
# Record usage snapshot every 10 minutes
*/10 * * * * curl -s http://localhost:58080/api/usage/snapshot > /dev/null
```

### Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12 / Flask / Flask-SocketIO |
| Database | SQLite3 |
| Frontend | Vanilla HTML/CSS/JS (no framework, zero CDN deps) |
| Terminal | xterm.js + Socket.IO |
| Remote Ops | SSH + sshpass |

### Project Structure

```
licman/
├── app/
│   ├── server.py           # Route & API entry
│   ├── config.py           # Config CRUD
│   ├── vendor.py           # Vendor CRUD + DB init
│   ├── flexlm.py           # lmgrd/lmstat/lmdown/lmreread wrappers
│   ├── filesystem.py       # File browser (local + SSH)
│   ├── remote.py           # SSH file read/write abstraction
│   ├── license_parser.py   # License expiry parser
│   ├── license_writer.py   # DAEMON/SERVER line detection & injection
│   ├── host.py             # Host management
│   ├── settings.py         # Key-value settings store
│   ├── backup.py           # Backup/restore
│   ├── notify.py           # SMTP email notifications
│   ├── logger.py           # Operation log
│   ├── run.py              # Entry point
│   ├── static/             # CSS / JS / assets
│   └── templates/          # Jinja2 HTML templates (14 pages)
├── bin/licman              # Control script
├── python/                 # Embedded Python 3.12
├── install.sh              # Auto-configuring installer
└── data/                   # SQLite DB (auto-created)
```

### Requirements

- Python 3.8+ (embedded 3.12 included)
- Flask, Flask-SocketIO
- FlexLM utilities: lmgrd, lmstat, lmdown, lmreread
- sshpass (optional, for password-based SSH)
- SQLite3 (system built-in)

### License

MIT License — see [LICENSE](LICENSE) file.

---

## 中文

### 什么是 LicMan

面向 EDA 工程师的 FlexNet/FlexLM 许可证 Web 管理系统。一个浏览器面板管理多台主机上的 license server，不再需要 SSH 到每台机器手动编辑 license 文件。

### 安装与使用

同上 — 解压后运行 `./install.sh [-port PORT]`，然后 `./bin/licman start`，浏览器访问 `http://localhost:58080`。

### 功能概览

| 模块 | 功能 |
|---|---|
| 许可证管理 | 新建 / 编辑 / 克隆 / 删除 lmgrd 配置，启动 / 停止 / 重读 |
| 厂商管理 | 按主机分组管理 daemon 路径和 exclude 文件 |
| 用量监控 | 实时 feature 用量 + 用户列表 + 自动刷新 |
| 多主机 | SSH 远程：文件浏览、license 预览、DAEMON 检测、端口检测 |
| DAEMON 行 | 智能检测冲突 → 用户确认 → 自动写入 → .bak 备份 |
| 过期提醒 | 解析 license 到期日，仪表盘告警 |
| 邮件通知 | SMTP 配置，过期或使用率超 90% 自动发邮件 |
| 使用率趋势 | 双视图（按厂商 / 按 Feature），柱状图 |
| 备份还原 | JSON 一键导出/导入，CSV 报表 |
| Web 终端 | 浏览器内操作 shell |

### 作者

EDA 运维工程师 + Claude (Anthropic) 协同开发。

### 许可证

MIT License — 任意使用、修改、分发。
