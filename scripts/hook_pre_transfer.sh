#!/bin/bash
#
# Hermit Crab - 迁移前钩子脚本
# 在开始迁移前在源服务器上执行
#

set -e

echo "========================================"
echo "执行迁移前钩子"
echo "========================================"

# 获取目标服务器IP（作为参数传入）
TARGET_IP="${1:-}"

if [ -z "$TARGET_IP" ]; then
    echo "错误: 未指定目标服务器IP"
    exit 1
fi

echo "目标服务器: $TARGET_IP"

# 1. 停止可能干扰迁移的服务
echo "停止可能干扰迁移的服务..."
# systemctl stop some-service || true

# 2. 数据库备份（如果启用）
echo "检查数据库备份需求..."

# MySQL备份
if systemctl is-active --quiet mysql; then
    echo "备份MySQL数据库..."
    mysqldump --all-databases > /tmp/mysql_backup.sql || true
fi

# Redis备份
if systemctl is-active --quiet redis; then
    echo "备份Redis数据..."
    redis-cli save || true
fi

# 3. 清理临时文件和缓存
echo "清理临时文件..."
rm -rf /tmp/* 2>/dev/null || true
rm -rf /var/tmp/* 2>/dev/null || true

# 4. 确保重要目录存在
echo "确保重要目录存在..."
mkdir -p /opt/hermit_crab/{config,data,logs,scripts}

# 5. 生成迁移元数据
echo "生成迁移元数据..."
cat > /opt/hermit_crab/data/migration_meta.json <<EOF
{
    "migration_start": "$(date -Iseconds)",
    "source_ip": "$(curl -s ifconfig.me || hostname -I | awk '{print $1}')",
    "target_ip": "$TARGET_IP",
    "source_hostname": "$(hostname)"
}
EOF

echo "✅ 迁移前钩子执行完成"
echo "========================================"

exit 0

