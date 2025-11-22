# Hermit Crab - 寄居蟹自动迁移系统

自动化服务器整机克隆与热迁移系统，像寄居蟹换壳一样自动迁移到新服务器。

## 🎯 核心功能

- **自动整机迁移**：服务器即将到期时自动迁移到新服务器
- **DNS自动切换**：迁移完成后自动更新 CloudFlare DNS
- **无限迁移链**：A → B → C → D... 无限循环
- **GitHub同步**：多服务器通过 GitHub 共享服务器池
- **零停机迁移**：Rsync 增量同步，最小化服务中断

## 📦 安装

```bash
cd /root/hermit_crab
./install.sh
```

安装脚本会自动：
- 安装系统依赖（rsync, python3, ssh 等）
- 安装 Python 依赖
- 配置 systemd 定时器

## ⚙️ 配置

所有配置在 `.env` 文件中管理：

```bash
cd /root/hermit_crab
cp env.example .env
nano .env
```

### 必需配置

```bash
# 业务域名（DNS会更新到新服务器）
HERMIT_CURRENT_DOMAIN=a.ssfxx.com

# SSH密码（必需！即使使用密钥，首次连接也需要密码）
HERMIT_SSH_PASSWORD=your_password

# 或为每台服务器配置不同密码
# HERMIT_SSH_PASSWORD=192.168.1.11:pass1|192.168.1.12:pass2
```

### 可选配置

```bash
# GitHub 中心化管理（推荐）
HERMIT_GITHUB_ENABLED=true
HERMIT_GITHUB_REPO=your-username/hermit-nodes
HERMIT_GITHUB_TOKEN=ghp_xxxxx

# CloudFlare DNS 自动更新（推荐）
HERMIT_CF_ENABLED=true
HERMIT_CF_ZONE_ID=your_zone_id
HERMIT_CF_TOKEN=your_cf_token
HERMIT_CF_DOMAIN=ssfxx.com

# 服务器生命周期
HERMIT_TOTAL_DAYS=15              # 服务器总生命周期（天）
HERMIT_MIGRATE_THRESHOLD=5        # 剩余N天时触发迁移
```

## 🚀 快速开始

### 1. 初始化当前服务器

```bash
python3 agent.py init
# 系统自动记录当前时间，domain 从 .env 读取
```

### 2. 添加备用服务器

```bash
python3 agent.py add --ip 192.168.1.11
python3 agent.py add --ip 192.168.1.12 --notes "备份服务器"
# 系统自动记录添加时间
```

### 3. 删除服务器

```bash
python3 agent.py remove --ip 192.168.1.11
# 从本地和 GitHub 中删除服务器
```

### 4. 启用自动监控

```bash
systemctl enable hermit-crab.timer
systemctl start hermit-crab.timer
# 每小时自动检查，剩余时间不足时自动迁移
```

## 📝 常用命令

```bash
# 查看状态
python3 agent.py status

# 检查是否需要迁移
python3 agent.py check

# 列出所有服务器
python3 agent.py list

# 添加服务器
python3 agent.py add --ip 192.168.1.11 --notes "备份服务器"

# 删除服务器
python3 agent.py remove --ip 192.168.1.11

# 手动迁移到指定服务器
python3 agent.py migrate --target 192.168.1.11

# 自动选择目标并迁移
python3 agent.py migrate --auto

# 强制迁移到剩余时间最长的服务器（忽略生命周期检查）
python3 agent.py migrate --auto --force

# 守护进程模式（持续监控）
python3 agent.py daemon
```

## 🔄 工作流程

```
服务器 A (IP: 192.168.1.10, 剩余 4 天)
业务域名: a.ssfxx.com → 192.168.1.10
    ↓
1. 检测到剩余天数 ≤ 阈值 (5天)
2. 从服务器池中自动选择服务器 B (剩余 14 天)
3. 获取分布式锁（防止多服务器同时选择）
4. Rsync 整机克隆：A → B
5. 更新 CloudFlare DNS: a.ssfxx.com → 192.168.1.11 ✅
6. 初始化服务器 B，自动配置
7. 服务器 B 启动定时监控
    ↓
服务器 B (剩余 4 天) → 自动迁移到 C → 无限循环...
业务域名始终是 a.ssfxx.com，只是 IP 在变化
```

## 📊 数据结构

### nodes.json（服务器池）

```json
{
  "servers": [
    {
      "ip": "192.168.1.10",
      "added_date": "2025-11-21",
      "status": "active",
      "notes": "当前服务器"
    },
    {
      "ip": "192.168.1.11",
      "added_date": "2025-11-21",
      "status": "idle",
      "notes": "备用服务器"
    }
  ]
}
```

- **过期时间**：自动计算 = `added_date + HERMIT_TOTAL_DAYS`
- **唯一标识**：IP 地址
- **状态**：`idle`（空闲）、`active`（使用中）、`transferring`（迁移中）

## 🔐 安全说明

### SSH 密码配置

**重要**：即使使用 SSH 密钥，密码也必须配置！因为首次连接新服务器需要密码认证。

```bash
# 方式1：所有服务器相同密码
HERMIT_SSH_PASSWORD=common_password

# 方式2：每台服务器不同密码（推荐）
HERMIT_SSH_PASSWORD=192.168.1.11:pass1|192.168.1.12:pass2|192.168.1.13:pass3
```

### 密码自动传播

`.env` 文件会随迁移自动复制到新服务器，实现密码的自动传播，无需手动配置。

## 🛡️ 排除列表

系统自动排除以下内容（避免破坏目标服务器）：

- 虚拟文件系统：`/proc`, `/sys`, `/dev`
- 网络配置：`/etc/netplan`, `/etc/network`
- 引导文件：`/boot`, `/lib/modules`
- 临时文件：`/tmp`, `/var/tmp`

详见：`config/exclude_list.txt`

## 📋 迁移日志

每次迁移会生成独立的详细日志文件：

```bash
# 日志位置
/root/hermit_crab/logs/migrations/migration_YYYYMMDD_HHMMSS.log

# 日志内容包括
- 迁移开始/结束时间
- 源服务器和目标服务器信息
- SSH 连接测试详情
- 文件传输统计（每100个文件记录一次）
- DNS 更新记录
- 错误和警告信息
- 总耗时统计

# 查看最近的迁移日志
ls -lt /root/hermit_crab/logs/migrations/ | head -5
tail -f /root/hermit_crab/logs/migrations/migration_*.log
```

**注意**：Rsync 传输进度实时显示在终端，但不完整记录到日志文件（避免日志文件过大）。

## 🐛 调试模式

```bash
# 在 .env 中设置
HERMIT_DEBUG=true
HERMIT_DRY_RUN=true       # 测试模式，不实际执行迁移
HERMIT_SKIP_REBOOT=true   # 跳过重启
```

## 📖 环境变量完整列表

查看 `env.example` 了解所有可配置项。

### 基本配置
- `HERMIT_CURRENT_DOMAIN` - 业务域名
- `HERMIT_LOG_LEVEL` - 日志级别 (DEBUG/INFO/WARNING/ERROR)

### 生命周期
- `HERMIT_TOTAL_DAYS` - 服务器总生命周期（天）
- `HERMIT_MIGRATE_THRESHOLD` - 触发迁移阈值（天）
- `HERMIT_CHECK_INTERVAL` - 检查间隔（秒）

### GitHub
- `HERMIT_GITHUB_ENABLED` - 是否启用
- `HERMIT_GITHUB_REPO` - 仓库名（username/repo）
- `HERMIT_GITHUB_TOKEN` - API Token

### CloudFlare
- `HERMIT_CF_ENABLED` - 是否启用
- `HERMIT_CF_ZONE_ID` - Zone ID
- `HERMIT_CF_TOKEN` - API Token
- `HERMIT_CF_DOMAIN` - 域名后缀

### SSH
- `HERMIT_SSH_USER` - SSH 用户名（默认 root）
- `HERMIT_SSH_PASSWORD` - SSH 密码
- `HERMIT_SSH_KEY_PATH` - SSH 私钥路径

### Rsync
- `HERMIT_RSYNC_BANDWIDTH_LIMIT` - 带宽限制（KB/s，0=不限制）
- `HERMIT_RSYNC_TIMEOUT` - 超时时间（秒）

## 🔧 卸载

```bash
./uninstall.sh
```

## 📄 License

MIT

## 🤝 Contributing

欢迎提交 Issue 和 Pull Request！

---

**注意**：本系统适合短期VPS的无缝迁移场景，不建议用于生产环境的关键业务。

