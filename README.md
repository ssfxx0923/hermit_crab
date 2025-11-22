# Hermit Crab - 寄居蟹自动迁移系统

自动化服务器整机克隆与热迁移系统，像寄居蟹换壳一样自动迁移到新服务器。

## 🎯 核心功能

- **自动整机迁移**：服务器即将到期时自动迁移到新服务器
- **DNS自动切换**：迁移完成后自动更新 CloudFlare DNS
- **邮件实时通知**：使用 Resend API 发送迁移状态通知
- **无限迁移链**：A → B → C → D... 无限循环
- **GitHub同步**：多服务器通过 GitHub 共享服务器池
- **零停机迁移**：Rsync 增量同步，最小化服务中断

---

## 📦 从零开始部署

### 步骤 1：下载项目

```bash
cd /root
git clone <your-repo-url> hermit_crab
cd hermit_crab
```

### 步骤 2：配置环境变量

```bash
cp env.example .env
nano .env
```

**必需配置**：

```bash
# 业务域名
HERMIT_CURRENT_DOMAIN=a.example.com

# 服务器寿命
HERMIT_TOTAL_DAYS=15
HERMIT_MIGRATE_THRESHOLD=5

# SSH密码（必需！）
HERMIT_SSH_PASSWORD=your_password
```

**推荐配置**：

```bash
# GitHub
HERMIT_GITHUB_ENABLED=true
HERMIT_GITHUB_REPO=username/hermit-nodes
HERMIT_GITHUB_TOKEN=ghp_xxxxx

# CloudFlare
HERMIT_CF_ENABLED=true
HERMIT_CF_ZONE_ID=xxx
HERMIT_CF_TOKEN=xxx
HERMIT_CF_DOMAIN=example.com

# 邮件
HERMIT_NOTIFICATION_ENABLED=true
HERMIT_RESEND_API_KEY=re_xxxxx
HERMIT_NOTIFICATION_FROM=HermitCrab@example.com
HERMIT_NOTIFICATION_TO=admin@example.com
```

### 步骤 3：安装

```bash
chmod +x install.sh
./install.sh
```

### 步骤 4：初始化

```bash
hermit-crab init
```

### 步骤 5：添加备用服务器

```bash
hermit-crab add --ip 104.248.191.16
hermit-crab add --ip 165.227.100.50 --notes "备份"
```

### 步骤 6：启动自动迁移

```bash
hermit-crab start
```

✅ 完成！系统会自动监控并在需要时执行迁移。

---

## 🎮 命令

### 自动迁移控制

```bash
# 启动自动迁移
hermit-crab start

# 停止自动迁移
hermit-crab stop

# 查看状态
hermit-crab status
```

### 服务器管理

```bash
# 列出服务器
hermit-crab list

# 添加服务器
hermit-crab add --ip 192.168.1.11
hermit-crab add --ip 192.168.1.12 --notes "备注"

# 删除服务器
hermit-crab remove --ip 192.168.1.11
```

### 迁移操作

```bash
# 检查是否需要迁移
hermit-crab check

# 手动迁移
hermit-crab migrate --target 192.168.1.11

# 自动选择并迁移
hermit-crab migrate --auto

# 强制迁移
hermit-crab migrate --auto --force
```

---

## 📊 状态显示

运行 `hermit-crab status`：

```
============================================================
Hermit Crab 服务器状态
============================================================
状态: ✅ HEALTHY
当前IP: 170.64.226.135
当前域名: a.example.com
添加日期: 2025-11-22
过期日期: 2025-12-07
剩余天数: 14 天
迁移次数: 0
需要迁移: 否
============================================================
自动迁移状态
============================================================
状态: ✅ 已启动
说明: 系统将自动监控并在需要时执行迁移
============================================================
```

**状态**：
- `✅ HEALTHY` - 健康
- `⚠️ WARNING` - 警告（< 10天）
- `🚨 CRITICAL` - 紧急（< 5天）
- `❌ EXPIRED` - 已过期

**自动迁移**：
- `✅ 已启动` - 自动监控中
- `❌ 未启动` - 需手动迁移

---

## 🔄 工作流程

```
服务器 A (剩余 4 天)
    ↓
检测剩余 ≤ 5 天
    ↓
选择服务器 B (剩余 14 天)
    ↓
Rsync 克隆 A → B
    ↓
更新 DNS
    ↓
初始化 B
    ↓
B 接管监控
    ↓
无限循环...
```

---

## 📧 邮件通知

| 类型 | 触发 |
|------|------|
| 🔄 迁移开始 | 开始迁移 |
| ✅ 迁移成功 | 完成迁移 |
| ❌ 迁移失败 | 迁移出错 |
| ⚠️ 生命周期警告 | 天数不足 |
| 🆕 服务器添加 | 添加服务器 |
| 🚨 无可用服务器 | 无目标 |

---

## 📋 服务器池

**文件**：`data/nodes.json`

```json
{
  "servers": [
    {
      "ip": "104.248.191.16",
      "added_date": "2025-11-22",
      "status": "active"
    },
    {
      "ip": "165.227.100.50",
      "added_date": "2025-11-22",
      "status": "idle"
    }
  ]
}
```

**状态**：`idle`, `active`, `transferring`, `dead`

---

## 🔐 安全

### SSH 密码

**必须配置**（首次连接需要）：

```bash
# 统一密码
HERMIT_SSH_PASSWORD=your_password

# 每台不同
HERMIT_SSH_PASSWORD=192.168.1.11:pass1|192.168.1.12:pass2
```

### 排除列表

自动排除：`/proc`, `/sys`, `/dev`, `/run`, `/tmp`, `/etc/netplan`, `/boot`, `/swap`

详见 `config/exclude_list.txt`

---

## 🐛 故障排除

### 日志

```bash
# 主日志
tail -f /root/hermit_crab/logs/hermit_crab.log

# 迁移日志
tail -f /root/hermit_crab/logs/migrations/migration_*.log

# 系统日志
journalctl -u hermit-crab-daemon.service -f
```

### 常见问题

**自动迁移没执行？**
```bash
hermit-crab status
hermit-crab start
```

**SSH 连接失败？**
```bash
grep HERMIT_SSH_PASSWORD .env
ssh root@目标IP
```

**迁移卡住？**
```bash
journalctl -u hermit-crab-daemon.service -f
df -h
```

---

## 📖 环境变量

### 基本
- `HERMIT_CURRENT_DOMAIN` - 域名
- `HERMIT_LOG_LEVEL` - 日志级别

### 生命周期
- `HERMIT_TOTAL_DAYS` - 总寿命（天）
- `HERMIT_MIGRATE_THRESHOLD` - 迁移阈值（天）

### GitHub
- `HERMIT_GITHUB_ENABLED` - 启用
- `HERMIT_GITHUB_REPO` - 仓库
- `HERMIT_GITHUB_TOKEN` - Token

### CloudFlare
- `HERMIT_CF_ENABLED` - 启用
- `HERMIT_CF_ZONE_ID` - Zone ID
- `HERMIT_CF_TOKEN` - Token
- `HERMIT_CF_DOMAIN` - 域名

### 邮件
- `HERMIT_NOTIFICATION_ENABLED` - 启用
- `HERMIT_RESEND_API_KEY` - API Key
- `HERMIT_NOTIFICATION_FROM` - 发件人
- `HERMIT_NOTIFICATION_TO` - 收件人

### SSH
- `HERMIT_SSH_USER` - 用户
- `HERMIT_SSH_PASSWORD` - 密码
- `HERMIT_SSH_KEY_PATH` - 密钥

查看 `env.example` 了解所有配置。

---

## 🔧 卸载

```bash
./uninstall.sh
```

---

## 📄 License

MIT

---

**注意**：适合短期VPS迁移，不建议生产关键业务使用。
