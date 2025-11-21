#!/bin/bash
#
# Hermit Crab - 迁移后钩子脚本
# 在迁移完成后在目标服务器上执行
#

set -e

echo "========================================"
echo "执行迁移后钩子"
echo "========================================"

# 1. 修复文件权限
echo "修复文件权限..."
chmod +x /opt/hermit_crab/agent.py 2>/dev/null || true
chmod +x /opt/hermit_crab/scripts/*.sh 2>/dev/null || true

# 2. 恢复关键配置文件
echo "恢复关键配置文件..."
if [ -d "/root/backup_before_migration" ]; then
    echo "发现备份目录，恢复网络配置..."
    
    # 恢复netplan
    if [ -d "/root/backup_before_migration/netplan" ]; then
        cp -a /root/backup_before_migration/netplan/* /etc/netplan/ 2>/dev/null || true
    fi
    
    # 恢复hostname
    if [ -f "/root/backup_before_migration/hostname" ]; then
        cp -a /root/backup_before_migration/hostname /etc/hostname 2>/dev/null || true
    fi
    
    # 恢复hosts
    if [ -f "/root/backup_before_migration/hosts" ]; then
        cp -a /root/backup_before_migration/hosts /etc/hosts 2>/dev/null || true
    fi
    
    # 应用网络配置
    netplan apply 2>/dev/null || true
fi

# 3. 修复动态库链接
echo "修复动态库链接..."
ldconfig 2>/dev/null || true

# 4. 修复APT包依赖
echo "修复APT包依赖..."
apt-get install -f -y 2>/dev/null || true

# 5. 重新生成SSH host keys（如果被覆盖）
echo "检查SSH host keys..."
if [ ! -f "/etc/ssh/ssh_host_rsa_key" ]; then
    echo "重新生成SSH host keys..."
    ssh-keygen -A
fi

# 6. 确保systemd服务配置正确
echo "配置systemd服务..."
systemctl daemon-reload
systemctl enable hermit-crab.service 2>/dev/null || true
systemctl enable hermit-crab.timer 2>/dev/null || true

# 7. 清理旧的日志
echo "清理旧日志..."
truncate -s 0 /opt/hermit_crab/logs/hermit_crab.log 2>/dev/null || true

# 8. 更新迁移元数据
if [ -f "/opt/hermit_crab/data/migration_meta.json" ]; then
    echo "更新迁移元数据..."
    
    # 添加完成时间
    TEMP_FILE=$(mktemp)
    jq '. + {"migration_complete": "'$(date -Iseconds)'"}' \
        /opt/hermit_crab/data/migration_meta.json > "$TEMP_FILE" 2>/dev/null || true
    
    if [ -f "$TEMP_FILE" ]; then
        mv "$TEMP_FILE" /opt/hermit_crab/data/migration_meta.json
    fi
fi

# 9. 启动服务（可选，通常重启后自动启动）
echo "启动Hermit Crab服务..."
# systemctl start hermit-crab.service || true

echo "✅ 迁移后钩子执行完成"
echo "========================================"

exit 0

