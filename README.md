# LicMan — FlexLM License Manager

开源 EDA 提效工具 — 多主机 FlexNet/FlexLM 许可证集中管理系统。

## 安装

```bash
tar -xzf licman-*.tar.gz -C /opt/
cd /opt/licman
./install.sh                # 默认 58080 端口
./install.sh -port 8080     # 指定端口
```

安装脚本自动：检测安装路径 → 更新 Python shebang 和配置文件路径 → 设置可执行权限 → 创建数据和日志目录。

## 使用

```bash
cd /opt/licman

./bin/licman start          # 启动
./bin/licman stop           # 停止
./bin/licman status         # 查看状态
./bin/licman restart        # 重启
./bin/licman cleandb        # 清空数据库 (需先停止)
```

浏览器访问: `http://localhost:58080`

## 功能

### 许可证管理
- 新增/编辑/删除/克隆 lmgrd 配置
- 启动、停止 (lmdown)、重读 (lmreread) 许可证
- 开机自启 (rc.local 自动写入)
- 命令预览：编辑时实时显示 lmgrd 命令行
- 文件浏览器：可视化选择 lmgrd 路径、license 文件、日志路径等

### 厂商管理
- 管理 Synopsys、Cadence 等 EDA 厂商的 daemon 配置
- 每厂商可设定默认 daemon 路径 (写入 DAEMON 行第3列)
- 每厂商可设定默认 Exclude/Options 文件 (写入 DAEMON 行第4列)
- 厂商可按主机分组：不同主机可有不同的 daemon 路径和 exclude 文件

### 用量监控
- 实时展示各 feature 的 license 总量、使用中、使用率
- 查看每个 feature 的当前用户列表 (用户名/主机/终端/版本)
- 自动刷新 (5s / 10s / 30s / 60s 可选)
- 使用率超 85% 仪表盘告警

### 多主机管理
- 添加多台主机 (IP、SSH 端口、用户名、密码)
- SSH 连通性测试
- 远程文件浏览、license 文件预览、DAEMON 行检测均通过 SSH 透明支持
- SSH ControlMaster 连接复用，减少握手开销
- 配置可按主机分组，仪表盘自动按主机拆分显示

### DAEMON 行自动写入
- 编辑配置后自动检测 license 文件中的 DAEMON/VENDOR 行
- 显示第 3 列 (daemon 路径) 和第 4 列 (exclude 文件) 的当前值与配置值的冲突
- 无冲突时自动填入，有冲突时提示用户确认后强制写入
- 写入前自动创建 `.bak` 备份
- 同时支持更新 SERVER 行第 2 列 (主机名)

### 许可证过期提醒
- 解析 license 文件中 INCREMENT/FEATURE 行的到期日
- 每配置显示最早过期项，在仪表盘以折叠面板展示
- 可配置告警天数 (全局设置)

### 邮件通知
- 配置 SMTP 后：许可证即将过期自动发邮件
- 使用率超 90% 自动发邮件
- 设置页可发送测试邮件验证配置

### 使用率趋势
- 双视图切换：按厂商查看 / 按 Feature 查看
- 柱状图展示 6h / 24h / 3d / 7d 的用量变化
- 手动记录快照或配置 cron 自动记录

### 数据管理
- 一键导出备份 (JSON，包含全部配置、厂商、主机、设置、日志)
- 一键导入还原 (支持合并/替换两种模式)
- CSV 报表导出 (包含所有用量快照记录)
- 配置克隆：一键复制现有配置，改个名字就能用

### 其他
- Web 终端：浏览器内直接操作服务器 shell
- Debug 日志实时 tail -f 查看器
- 操作日志：记录所有配置变更操作

## Cron 自动用量快照

```bash
# 每 10 分钟记录一次
*/10 * * * * curl -s http://localhost:58080/api/usage/snapshot > /dev/null

# 每天早上 9 点发送过期提醒邮件
0 9 * * * curl -s http://localhost:58080/api/expiry/alerts > /dev/null
```

## 文件结构

```
licman/
├── app/                   # Flask 应用
│   ├── server.py          # 路由入口
│   ├── config.py          # 配置 CRUD + lmgrd 命令构建
│   ├── vendor.py          # 厂商 CRUD + 数据库初始化
│   ├── flexlm.py          # FlexLM 命令 (lmgrd/lmstat/lmdown/lmreread)
│   ├── filesystem.py      # 文件浏览 (本地 + SSH 远程)
│   ├── remote.py           # SSH 文件读写抽象层
│   ├── license_parser.py  # License 文件过期解析
│   ├── license_writer.py  # DAEMON/SERVER 行检测与写入
│   ├── host.py            # 主机管理 CRUD
│   ├── settings.py        # 全局设置 KV
│   ├── backup.py          # 备份还原
│   ├── notify.py          # 邮件通知 (SMTP)
│   ├── logger.py          # 操作日志
│   ├── run.py             # 入口
│   ├── static/
│   │   ├── style.css      # 暗色主题样式
│   │   ├── app.js         # 前端逻辑
│   │   └── socket.io.js   # WebSocket 客户端
│   └── templates/         # Jinja2 页面模板
│       ├── base.html      # 顶栏布局
│       ├── dashboard.html # 仪表盘 (主机分组、过期告警)
│       ├── config_edit.html    # 配置编辑 (文件预览、DAEMON 检测)
│       ├── vendor_list.html    # 厂商管理 (主机分组)
│       ├── monitor.html        # 用量监控
│       ├── host_list.html      # 主机管理
│       ├── trends.html         # 使用率趋势 (双视图)
│       ├── settings.html       # 全局设置 + 备份还原 + 邮件
│       ├── logs.html           # 操作日志
│       ├── log_viewer.html     # Debug 日志 tail
│       └── terminal.html       # Web 终端
├── bin/licman             # 控制脚本 (start/stop/restart/status/cleandb)
├── python/                # 嵌入式 Python 3.12
├── install.sh             # 安装脚本
└── data/                  # SQLite 数据库 (自动创建)
```

## 依赖

- Python 3.8+ (附带嵌入式 3.12)
- Flask, Flask-SocketIO
- FlexLM 工具: lmgrd, lmstat, lmdown, lmreread
- sshpass (可选，远程主机密码认证)
- SQLite3 (系统自带)

## License

Internal use.
