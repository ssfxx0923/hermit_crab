#!/bin/bash
#
# Hermit Crab 安装脚本
# 自动安装所有依赖和配置系统
#

set -e

echo "========================================"
echo "Hermit Crab 安装程序"
echo "========================================"

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用root权限运行此脚本"
    exit 1
fi

# 安装路径
INSTALL_PATH="/opt/hermit_crab"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "当前目录: $CURRENT_DIR"
echo "安装路径: $INSTALL_PATH"

# 1. 更新系统包
echo ""
echo "步骤 1/8: 更新系统包..."
apt-get update -qq

# 2. 安装系统依赖
echo ""
echo "步骤 2/8: 安装系统依赖..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    rsync \
    openssh-server \
    openssh-client \
    sshpass \
    curl \
    wget \
    tar \
    gzip \
    jq \
    git

echo "✅ 系统依赖安装完成"

# 3. 安装Python依赖
echo ""
echo "步骤 3/8: 安装Python依赖..."

# 使用pip安装
if [ -f "$CURRENT_DIR/requirements.txt" ]; then
    # 先尝试不带标志安装（兼容老系统），失败则使用 --break-system-packages（新系统）
    # 添加 --ignore-installed 避免尝试卸载系统包
    pip3 install -r "$CURRENT_DIR/requirements.txt" 2>/dev/null || \
    pip3 install -r "$CURRENT_DIR/requirements.txt" --break-system-packages --ignore-installed
    echo "✅ Python依赖安装完成"
else
    echo "⚠️  requirements.txt 未找到，跳过Python依赖安装"
fi

# 4. 复制文件到安装路径
echo ""
echo "步骤 4/8: 复制文件到安装路径..."

if [ "$CURRENT_DIR" != "$INSTALL_PATH" ]; then
    # 创建安装目录
    mkdir -p "$INSTALL_PATH"
    
    # 复制所有文件
    cp -r "$CURRENT_DIR"/* "$INSTALL_PATH/"
    
    echo "✅ 文件复制完成"
else
    echo "✅ 已在安装路径中"
fi

# 确保目录结构存在
mkdir -p "$INSTALL_PATH"/{config,data,logs,scripts,modules,systemd}

# 5. 设置权限
echo ""
echo "步骤 5/8: 设置权限..."
chmod +x "$INSTALL_PATH/agent.py"
chmod +x "$INSTALL_PATH/scripts"/*.sh
chmod 600 "$INSTALL_PATH/config.yaml" 2>/dev/null || true

echo "✅ 权限设置完成"

# 6. 安装systemd服务
echo ""
echo "步骤 6/8: 安装systemd服务..."

# 复制服务文件
cp "$INSTALL_PATH/systemd/hermit-crab.service" /etc/systemd/system/
cp "$INSTALL_PATH/systemd/hermit-crab.timer" /etc/systemd/system/
cp "$INSTALL_PATH/systemd/hermit-crab-daemon.service" /etc/systemd/system/

# 重新加载systemd
systemctl daemon-reload

echo "✅ Systemd服务已安装"

# 7. 创建符号链接（可选）
echo ""
echo "步骤 7/8: 创建符号链接..."
ln -sf "$INSTALL_PATH/agent.py" /usr/local/bin/hermit-crab 2>/dev/null || true

echo "✅ 符号链接已创建"

# 8. 显示后续步骤
echo ""
echo "步骤 8/8: 安装完成！"
echo ""
echo "========================================"
echo "✅ Hermit Crab 安装成功！"
echo "========================================"
echo ""
echo "后续步骤:"
echo ""
echo "1. 配置环境变量 (可选，如果使用GitHub和CloudFlare):"
echo "   export HERMIT_GITHUB_TOKEN='your_github_token'"
echo "   export HERMIT_CF_TOKEN='your_cloudflare_token'"
echo "   # 建议添加到 /etc/environment 或 ~/.bashrc"
echo ""
echo "2. 编辑配置文件:"
echo "   nano $INSTALL_PATH/config.yaml"
echo ""
echo "3. 初始化生命周期:"
echo "   cd $INSTALL_PATH"
echo "   python3 agent.py init --added-date $(date +%Y-%m-%d) --domain your-domain.ssfxx.com"
echo ""
echo "4. 查看状态:"
echo "   python3 agent.py status"
echo ""
echo "5. 启用定时检查 (推荐):"
echo "   systemctl enable hermit-crab.timer"
echo "   systemctl start hermit-crab.timer"
echo ""
echo "6. 或者使用守护进程模式:"
echo "   systemctl enable hermit-crab-daemon.service"
echo "   systemctl start hermit-crab-daemon.service"
echo ""
echo "7. 运行健康检查:"
echo "   $INSTALL_PATH/scripts/health_check.sh"
echo ""
echo "更多信息请查看文档或运行: python3 agent.py --help"
echo "========================================"

exit 0

