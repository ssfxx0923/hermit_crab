#!/bin/bash
#
# Hermit Crab - 健康检查脚本
# 检查系统和服务状态
#

echo "========================================"
echo "Hermit Crab 健康检查"
echo "========================================"

EXIT_CODE=0

# 1. 检查配置文件
echo -n "检查配置文件... "
if [ -f "${HERMIT_INSTALL_PATH:-/root/hermit_crab}/config.yaml" ]; then
    echo "✅"
else
    echo "❌ 配置文件不存在"
    EXIT_CODE=1
fi

# 2. 检查Python环境
echo -n "检查Python环境... "
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo "✅ ($PYTHON_VERSION)"
else
    echo "❌ Python3未安装"
    EXIT_CODE=1
fi

# 3. 检查必要工具
echo "检查必要工具:"
for tool in rsync ssh sshpass tar curl; do
    echo -n "  - $tool... "
    if command -v $tool &>/dev/null; then
        echo "✅"
    else
        echo "❌ 未安装"
        EXIT_CODE=1
    fi
done

# 4. 检查Python依赖
echo -n "检查Python依赖... "
if python3 -c "import yaml, github, requests" 2>/dev/null; then
    echo "✅"
else
    echo "❌ 依赖未完全安装"
    EXIT_CODE=1
fi

# 5. 检查生命周期
echo -n "检查生命周期初始化... "
if [ -f "${HERMIT_INSTALL_PATH:-/root/hermit_crab}/data/lifecycle.json" ]; then
    echo "✅"
    
    # 显示剩余天数
    if command -v jq &>/dev/null; then
        EXPIRE_DATE=$(jq -r '.expire_date' ${HERMIT_INSTALL_PATH:-/root/hermit_crab}/data/lifecycle.json)
        CURRENT_DATE=$(date +%Y-%m-%d)
        
        if command -v python3 &>/dev/null; then
            REMAINING=$(python3 -c "from datetime import datetime; d1=datetime.strptime('$EXPIRE_DATE', '%Y-%m-%d'); d2=datetime.strptime('$CURRENT_DATE', '%Y-%m-%d'); print((d1-d2).days)")
            echo "  剩余天数: $REMAINING 天"
        fi
    fi
else
    echo "⚠️  未初始化"
fi

# 6. 检查服务状态
echo -n "检查systemd服务... "
if systemctl is-active --quiet hermit-crab.timer; then
    echo "✅ 运行中"
else
    echo "⚠️  未运行"
fi

# 7. 检查网络连接
echo -n "检查网络连接... "
if curl -s --max-time 5 ifconfig.me &>/dev/null; then
    PUBLIC_IP=$(curl -s ifconfig.me)
    echo "✅ (公网IP: $PUBLIC_IP)"
else
    echo "⚠️  网络可能有问题"
fi

# 8. 检查磁盘空间
echo -n "检查磁盘空间... "
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "✅ (已使用: ${DISK_USAGE}%)"
else
    echo "⚠️  磁盘空间不足 (已使用: ${DISK_USAGE}%)"
fi

echo "========================================"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 健康检查通过"
else
    echo "❌ 健康检查发现问题"
fi

exit $EXIT_CODE

