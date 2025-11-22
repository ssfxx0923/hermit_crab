#!/bin/bash
#
# Hermit Crab 卸载脚本
#

set -e

echo "========================================"
echo "Hermit Crab 卸载程序"
echo "========================================"

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用root权限运行此脚本"
    exit 1
fi

# 确认卸载
read -p "确认要卸载 Hermit Crab 吗? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "取消卸载"
    exit 0
fi

INSTALL_PATH="/root/hermit_crab"

# 1. 停止并禁用服务
echo ""
echo "停止服务..."
systemctl stop hermit-crab.timer 2>/dev/null || true
systemctl stop hermit-crab.service 2>/dev/null || true
systemctl stop hermit-crab-daemon.service 2>/dev/null || true

systemctl disable hermit-crab.timer 2>/dev/null || true
systemctl disable hermit-crab.service 2>/dev/null || true
systemctl disable hermit-crab-daemon.service 2>/dev/null || true

# 2. 删除systemd服务文件
echo "删除systemd服务..."
rm -f /etc/systemd/system/hermit-crab.service
rm -f /etc/systemd/system/hermit-crab.timer
rm -f /etc/systemd/system/hermit-crab-daemon.service

systemctl daemon-reload

# 3. 删除符号链接
echo "删除符号链接..."
rm -f /usr/local/bin/hermit-crab

# 4. 备份配置和数据（可选）
read -p "是否备份配置和数据到 /root/hermit_crab_backup? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "备份数据..."
    mkdir -p /root/hermit_crab_backup
    cp -r "$INSTALL_PATH/config.yaml" /root/hermit_crab_backup/ 2>/dev/null || true
    cp -r "$INSTALL_PATH/data" /root/hermit_crab_backup/ 2>/dev/null || true
    cp -r "$INSTALL_PATH/logs" /root/hermit_crab_backup/ 2>/dev/null || true
    echo "✅ 数据已备份到 /root/hermit_crab_backup"
fi

# 5. 删除安装目录
echo "删除安装目录..."
rm -rf "$INSTALL_PATH"

echo ""
echo "========================================"
echo "✅ Hermit Crab 已卸载"
echo "========================================"
echo ""
echo "注意: Python包未被卸载，如需卸载请手动执行:"
echo "  pip3 uninstall PyYAML PyGithub requests cloudflare paramiko python-dateutil colorlog psutil"
echo ""

exit 0

