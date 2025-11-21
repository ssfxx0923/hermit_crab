# Hermit Crab 使用指南

## 完整使用流程示例

### 场景：配置3台服务器的自动迁移链

假设你有3台Ubuntu 25.04服务器：
- Server A (当前): 192.168.1.10, a.ssfxx.com, 到期时间: 2025-11-25 (剩余4天)
- Server B: 192.168.1.11, b.ssfxx.com, 到期时间: 2025-12-05 (剩余14天)
- Server C: 192.168.1.12, c.ssfxx.com, 到期时间: 2025-12-15 (剩余24天)

---

## 第一步：在Server A上安装和初始化

### 1.1 下载或克隆项目

```bash
# 假设项目已经在 /root/hermit_crab
cd /root/hermit_crab
```

### 1.2 运行安装脚本

```bash
chmod +x install.sh
./install.sh
```

安装脚本会自动：
- 安装系统依赖（rsync, ssh, python3等）
- 安装Python依赖包
- 复制文件到 /opt/hermit_crab
- 安装systemd服务
- 设置权限

### 1.3 配置环境变量

```bash
cd /opt/hermit_crab
chmod +x setup_env.sh
./setup_env.sh
```

按提示输入：
- GitHub Token (用于中心化管理服务器列表)
- CloudFlare API Token (用于自动更新DNS)
- 当前服务器域名: a.ssfxx.com

### 1.4 编辑配置文件

```bash
nano config.yaml
```

重点修改：
```yaml
github:
  repo: "your-username/hermit-nodes"  # 你的GitHub仓库

cloudflare:
  zone_id: "your_zone_id"  # 你的CloudFlare Zone ID
  domain: "ssfxx.com"

base:
  current_domain: "a.ssfxx.com"
```

### 1.5 初始化生命周期

```bash
python3 agent.py init --added-date 2025-11-06 --domain a.ssfxx.com
```

### 1.6 配置服务器列表

编辑 `data/nodes.json`：

```json
{
  "version": "1.0",
  "last_updated": "2025-11-21T00:00:00Z",
  "servers": [
    {
      "id": "server-001",
      "ip": "192.168.1.10",
      "domain": "a.ssfxx.com",
      "added_date": "2025-11-06",
      "expire_date": "2025-11-25",
      "status": "active",
      "last_heartbeat": "2025-11-21T00:00:00Z",
      "notes": "Current server"
    },
    {
      "id": "server-002",
      "ip": "192.168.1.11",
      "domain": "b.ssfxx.com",
      "added_date": "2025-11-06",
      "expire_date": "2025-12-05",
      "status": "idle",
      "last_heartbeat": null,
      "notes": "Target server 1"
    },
    {
      "id": "server-003",
      "ip": "192.168.1.12",
      "domain": "c.ssfxx.com",
      "added_date": "2025-11-06",
      "expire_date": "2025-12-15",
      "status": "idle",
      "last_heartbeat": null,
      "notes": "Target server 2"
    }
  ]
}
```

或者使用命令添加：

```bash
python3 agent.py add --ip 192.168.1.11 --domain b.ssfxx.com \
    --added-date 2025-11-06 --expire-date 2025-12-05 --notes "Target 1"

python3 agent.py add --ip 192.168.1.12 --domain c.ssfxx.com \
    --added-date 2025-11-06 --expire-date 2025-12-15 --notes "Target 2"
```

### 1.7 推送到GitHub（如果使用GitHub同步）

如果你手动编辑了 nodes.json，需要手动推送到GitHub：

```bash
# 在GitHub上创建仓库 your-username/hermit-nodes
# 上传 nodes.json 到仓库根目录
```

### 1.8 查看状态

```bash
python3 agent.py status
```

输出示例：
```
============================================================
Hermit Crab 服务器状态
============================================================
状态: 🚨 CRITICAL
当前IP: 192.168.1.10
当前域名: a.ssfxx.com
添加日期: 2025-11-06
过期日期: 2025-11-25
剩余天数: 4 天
迁移次数: 0
需要迁移: 是
============================================================
```

---

## 第二步：准备目标服务器 (Server B 和 C)

在Server B和Server C上，确保：

### 2.1 SSH服务运行

```bash
systemctl start sshd
systemctl enable sshd
```

### 2.2 允许root SSH登录（临时，首次迁移需要）

编辑 `/etc/ssh/sshd_config`：

```bash
PermitRootLogin yes
PasswordAuthentication yes
```

重启SSH：
```bash
systemctl restart sshd
```

### 2.3 确保有足够的磁盘空间

```bash
df -h
```

确保根分区至少有当前服务器使用空间的1.5倍。

---

## 第三步：执行迁移

回到Server A。

### 3.1 手动测试迁移（推荐第一次）

```bash
python3 agent.py check
```

确认需要迁移后：

```bash
python3 agent.py migrate --auto --password 'server_b_root_password'
```

参数说明：
- `--auto`: 自动选择最佳目标服务器
- `--password`: Server B的root密码（首次需要）

或者手动指定目标：

```bash
python3 agent.py migrate --target 192.168.1.11 --password 'password'
```

### 3.2 迁移过程

迁移会自动执行：

1. ✅ SSH连接测试
2. ✅ 配置SSH密钥免密登录
3. ✅ 备份目标服务器关键文件
4. ✅ Rsync系统文件同步（可能需要30分钟-2小时）
5. ✅ 恢复网络配置
6. ✅ Tar Stream传输大目录
7. ✅ 初始化目标服务器
8. ✅ 重启目标服务器
9. ✅ 更新DNS（a.ssfxx.com -> 192.168.1.11）
10. ✅ 等待反馈

### 3.3 迁移完成

当看到：

```
============================================================
🎉 迁移流程全部完成！
============================================================
新服务器: b.ssfxx.com (192.168.1.11)
请等待新服务器的反馈...
```

表示迁移成功！

---

## 第四步：启用自动监控

### 4.1 使用Timer定时检查（推荐）

```bash
systemctl enable hermit-crab.timer
systemctl start hermit-crab.timer
```

这会每小时自动检查一次，当需要迁移时自动执行。

查看定时器状态：
```bash
systemctl status hermit-crab.timer
journalctl -u hermit-crab.service -f
```

### 4.2 或使用守护进程模式

```bash
systemctl enable hermit-crab-daemon.service
systemctl start hermit-crab-daemon.service
```

查看守护进程状态：
```bash
systemctl status hermit-crab-daemon
journalctl -u hermit-crab-daemon -f
```

---

## 第五步：Server B 自动迁移到 Server C

当Server B运行到剩余4天时，会自动：

1. 检测到需要迁移
2. 从GitHub同步服务器列表
3. 选择Server C (剩余时间最长)
4. 获取Server C的锁（防止冲突）
5. 执行整机克隆
6. 更新DNS (a.ssfxx.com -> 192.168.1.12)
7. Server C启动并继续监控

这样就实现了 A → B → C 的无限扩散！

---

## 常见操作

### 列出所有服务器

```bash
python3 agent.py list
```

### 查看当前状态

```bash
python3 agent.py status
```

### 健康检查

```bash
/opt/hermit_crab/scripts/health_check.sh
```

### 查看日志

```bash
tail -f /opt/hermit_crab/logs/hermit_crab.log
```

### 手动同步GitHub

```python
# 在Python中
from modules import GitHubSync, load_config
config = load_config()
github = GitHubSync(config)
nodes = github.pull_nodes()
print(nodes)
```

### 手动更新DNS

```bash
# 在Python中
from modules import CloudFlareAPI, load_config
config = load_config()
cf = CloudFlareAPI(config)
cf.update_dns_record('a', '192.168.1.11')
```

---

## 故障排查

### 问题1：迁移失败，SSH连接超时

**解决**：
- 检查目标服务器SSH服务是否运行
- 检查防火墙规则
- 确认密码正确

### 问题2：Rsync传输中断

**解决**：
- Rsync支持断点续传，重新运行迁移命令即可
- 检查网络连接稳定性

### 问题3：目标服务器重启后无法访问

**解决**：
- 检查 `/root/backup_before_migration` 是否有备份
- 手动恢复网络配置
- 运行 `hook_post_transfer.sh` 脚本

### 问题4：DNS没有更新

**解决**：
- 检查CloudFlare Token是否正确
- 手动在CloudFlare面板更新DNS
- 查看日志：`/opt/hermit_crab/logs/hermit_crab.log`

### 问题5：GitHub同步失败

**解决**：
- 检查Token权限（需要repo权限）
- 检查仓库是否存在
- 手动编辑本地 `data/nodes.json`

---

## 安全建议

1. **SSH密钥管理**：
   - 迁移完成后，禁用密码登录
   - 定期轮换SSH密钥

2. **API Token保护**：
   - 使用环境变量，不要硬编码
   - 定期更新Token
   - 使用最小权限原则

3. **网络安全**：
   - 配置防火墙规则
   - 使用VPN或内网传输
   - 限制SSH访问来源

4. **数据备份**：
   - 迁移前备份重要数据
   - 保留旧服务器几天以防万一
   - 定期测试恢复流程

---

## 卸载

```bash
cd /opt/hermit_crab
chmod +x uninstall.sh
./uninstall.sh
```

会提示是否备份配置和数据。

---

## 技术支持

如有问题，请检查：
1. 日志文件：`/opt/hermit_crab/logs/hermit_crab.log`
2. 系统日志：`journalctl -u hermit-crab.service`
3. 运行健康检查：`/opt/hermit_crab/scripts/health_check.sh`

