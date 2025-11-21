# Hermit Crab - 寄居蟹自动迁移系统

自动化服务器整机克隆与热迁移系统，适用于短期服务器自动续命。

## 快速开始

### 1. 安装

```bash
cd /root/hermit_crab
chmod +x install.sh
./install.sh
```

### 2. 配置环境变量

```bash
chmod +x setup_env.sh
./setup_env.sh
```

### 3. 初始化

```bash
cd /opt/hermit_crab
python3 agent.py init --added-date 2025-11-21 --domain a.ssfxx.com
```

### 4. 启用自动检查

```bash
systemctl enable hermit-crab.timer
systemctl start hermit-crab.timer
```

## 主要命令

```bash
# 查看状态
python3 agent.py status

# 检查是否需要迁移
python3 agent.py check

# 手动迁移
python3 agent.py migrate --target 192.168.1.11 --password xxx

# 自动迁移
python3 agent.py migrate --auto --password xxx

# 添加服务器
python3 agent.py add --ip 192.168.1.12 --domain server-3.ssfxx.com \
    --added-date 2025-11-21 --expire-date 2025-12-06

# 列出服务器
python3 agent.py list
```

## 项目结构

```
/opt/hermit_crab/
├── agent.py              # 主程序
├── config.yaml           # 配置文件
├── requirements.txt      # Python依赖
├── modules/              # 核心模块
│   ├── monitor.py        # 监控模块
│   ├── scanner.py        # 服务器扫描
│   ├── migrator.py       # 迁移执行
│   ├── initializer.py    # 初始化器
│   ├── github_sync.py    # GitHub同步
│   └── cloudflare_api.py # CloudFlare DNS
├── config/               # 配置目录
│   └── exclude_list.txt  # Rsync排除列表
├── data/                 # 数据目录
│   ├── nodes.json        # 服务器列表
│   └── lifecycle.json    # 生命周期信息
├── logs/                 # 日志目录
├── scripts/              # 辅助脚本
│   ├── health_check.sh   # 健康检查
│   ├── hook_pre_transfer.sh
│   └── hook_post_transfer.sh
└── systemd/              # 系统服务
    ├── hermit-crab.service
    ├── hermit-crab.timer
    └── hermit-crab-daemon.service
```

## 核心特性

- ✅ 自动监控服务器生命周期
- ✅ 智能选择目标服务器
- ✅ Rsync + Tar Stream 分层传输
- ✅ GitHub 中心化管理
- ✅ CloudFlare DNS 自动更新
- ✅ 分布式锁防止并发冲突
- ✅ 自动初始化和配置新服务器
- ✅ 完整的反馈闭环

## 注意事项

1. 所有服务器必须是相同的Ubuntu版本
2. 首次连接需要提供SSH密码
3. 确保目标服务器有足够的磁盘空间
4. 建议在测试环境先验证
5. 迁移过程中会中断服务

## License

MIT

