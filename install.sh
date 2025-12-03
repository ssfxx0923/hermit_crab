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
INSTALL_PATH="/root/hermit_crab"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "当前目录: $CURRENT_DIR"
echo "安装路径: $INSTALL_PATH"

# 1. 更新系统包
echo ""
echo "步骤 1/9: 更新系统包..."
apt-get update -qq

# 2. 安装系统依赖
echo ""
echo "步骤 2/9: 安装系统依赖..."
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

# 3. 复制文件到安装路径
echo ""
echo "步骤 3/9: 复制文件到安装路径..."

if [ "$CURRENT_DIR" != "$INSTALL_PATH" ]; then
    # 创建安装目录
    mkdir -p "$INSTALL_PATH"

    # 复制所有文件（排除虚拟环境目录）
    rsync -av --exclude='venv' "$CURRENT_DIR/" "$INSTALL_PATH/"

    echo "✅ 文件复制完成"
else
    echo "✅ 已在安装路径中"
fi

# 确保目录结构存在
mkdir -p "$INSTALL_PATH"/{config,data,logs,scripts,modules,systemd}

# 4. 创建Python虚拟环境
echo ""
echo "步骤 4/9: 创建Python虚拟环境..."
VENV_PATH="$INSTALL_PATH/venv"

# 如果虚拟环境已存在，先删除
if [ -d "$VENV_PATH" ]; then
    echo "检测到已存在的虚拟环境，正在删除..."
    rm -rf "$VENV_PATH"
fi

# 创建虚拟环境
python3 -m venv "$VENV_PATH"
echo "✅ 虚拟环境创建完成: $VENV_PATH"

# 5. 安装Python依赖到虚拟环境
echo ""
echo "步骤 5/9: 在虚拟环境中安装Python依赖..."

if [ -f "$INSTALL_PATH/requirements.txt" ]; then
    # 激活虚拟环境并安装依赖
    source "$VENV_PATH/bin/activate"
    pip install --upgrade pip
    pip install -r "$INSTALL_PATH/requirements.txt"
    deactivate
    echo "✅ Python依赖安装完成"
else
    echo "⚠️  requirements.txt 未找到，跳过Python依赖安装"
fi

# 6. 设置权限
echo ""
echo "步骤 6/9: 设置权限..."
chmod +x "$INSTALL_PATH/agent.py"
chmod +x "$INSTALL_PATH/scripts"/*.sh
chmod 600 "$INSTALL_PATH/config.yaml" 2>/dev/null || true

echo "✅ 权限设置完成"

# 7. 安装systemd服务
echo ""
echo "步骤 7/9: 安装systemd服务..."

# 复制服务文件
cp "$INSTALL_PATH/systemd/hermit-crab.service" /etc/systemd/system/
cp "$INSTALL_PATH/systemd/hermit-crab.timer" /etc/systemd/system/
cp "$INSTALL_PATH/systemd/hermit-crab-daemon.service" /etc/systemd/system/

# 重新加载systemd
systemctl daemon-reload

echo "✅ Systemd服务已安装"

# 8. 创建符号链接（使用虚拟环境）
echo ""
echo "步骤 8/9: 创建符号链接..."

# 创建包装脚本以使用虚拟环境
cat > /usr/local/bin/hermit-crab << 'EOF'
#!/bin/bash
VENV_PATH="/root/hermit_crab/venv"
source "$VENV_PATH/bin/activate"
python /root/hermit_crab/agent.py "$@"
deactivate
EOF

chmod +x /usr/local/bin/hermit-crab
echo "✅ 符号链接已创建"

# 9. 显示后续步骤
echo ""
echo "步骤 9/9: 安装完成！"
echo ""
echo "========================================"
echo "✅ Hermit Crab 安装成功！"
echo "========================================"
echo ""
echo "后续步骤:"
echo ""
echo "1. 配置环境变量:"
echo "   cd $INSTALL_PATH"
echo "   nano .env"
echo "   # 填入 GitHub Token, CloudFlare Token 和 SSH 密码"
echo ""
echo "2. 初始化生命周期:"
echo "   hermit-crab init"
echo ""
echo "3. 添加备用服务器:"
echo "   hermit-crab add --ip <服务器IP>"
echo ""
echo "4. 查看状态:"
echo "   hermit-crab status"
echo ""
echo "5. 启动自动迁移 (推荐):"
echo "   hermit-crab start"
echo ""
echo "6. 手动执行迁移:"
echo "   hermit-crab migrate --auto"
echo ""
echo "更多信息请查看: hermit-crab --help"
echo "========================================"

exit 0

