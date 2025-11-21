#!/bin/bash
#
# Hermit Crab 环境变量配置脚本
# 帮助快速配置GitHub和CloudFlare的API Token
#

set -e

echo "========================================"
echo "Hermit Crab 环境变量配置"
echo "========================================"

ENV_FILE="/etc/environment"
PROFILE_FILE="/root/.bashrc"

# 函数：添加环境变量
add_env_variable() {
    local VAR_NAME="$1"
    local VAR_VALUE="$2"
    local FILE="$3"
    
    # 检查是否已存在
    if grep -q "^${VAR_NAME}=" "$FILE" 2>/dev/null; then
        # 更新现有变量
        sed -i "s|^${VAR_NAME}=.*|${VAR_NAME}=\"${VAR_VALUE}\"|" "$FILE"
        echo "✅ 已更新 $VAR_NAME 到 $FILE"
    else
        # 添加新变量
        echo "${VAR_NAME}=\"${VAR_VALUE}\"" >> "$FILE"
        echo "✅ 已添加 $VAR_NAME 到 $FILE"
    fi
}

# 1. 配置GitHub Token
echo ""
echo "1. GitHub Token 配置"
echo "   用于中心化管理服务器列表"
echo ""
read -p "是否配置 GitHub Token? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "请输入 GitHub Token: " GITHUB_TOKEN
    
    if [ -n "$GITHUB_TOKEN" ]; then
        add_env_variable "HERMIT_GITHUB_TOKEN" "$GITHUB_TOKEN" "$ENV_FILE"
        add_env_variable "HERMIT_GITHUB_TOKEN" "$GITHUB_TOKEN" "$PROFILE_FILE"
        export HERMIT_GITHUB_TOKEN="$GITHUB_TOKEN"
    fi
fi

# 2. 配置CloudFlare Token
echo ""
echo "2. CloudFlare API Token 配置"
echo "   用于自动更新DNS解析"
echo ""
read -p "是否配置 CloudFlare API Token? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "请输入 CloudFlare API Token: " CF_TOKEN
    
    if [ -n "$CF_TOKEN" ]; then
        add_env_variable "HERMIT_CF_TOKEN" "$CF_TOKEN" "$ENV_FILE"
        add_env_variable "HERMIT_CF_TOKEN" "$CF_TOKEN" "$PROFILE_FILE"
        export HERMIT_CF_TOKEN="$CF_TOKEN"
    fi
fi

# 3. 配置其他选项
echo ""
echo "3. 其他配置"
echo ""
read -p "是否配置当前服务器域名? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "请输入当前服务器域名 (例如: a.ssfxx.com): " CURRENT_DOMAIN
    
    if [ -n "$CURRENT_DOMAIN" ]; then
        # 更新config.yaml
        CONFIG_FILE="/opt/hermit_crab/config.yaml"
        if [ -f "$CONFIG_FILE" ]; then
            sed -i "s|current_domain:.*|current_domain: \"$CURRENT_DOMAIN\"|" "$CONFIG_FILE"
            echo "✅ 已更新配置文件中的域名"
        fi
    fi
fi

echo ""
echo "========================================"
echo "✅ 环境变量配置完成"
echo "========================================"
echo ""
echo "环境变量已添加到:"
echo "  - $ENV_FILE (系统级)"
echo "  - $PROFILE_FILE (用户级)"
echo ""
echo "重新加载环境变量:"
echo "  source $PROFILE_FILE"
echo ""
echo "验证配置:"
echo "  echo \$HERMIT_GITHUB_TOKEN"
echo "  echo \$HERMIT_CF_TOKEN"
echo ""

exit 0

