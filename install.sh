#!/usr/bin/env bash
#
# Claude Code 插件自动管理器 - 安装脚本
# 在新机器上克隆仓库后运行此脚本自动配置
#

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# 检测当前目录
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="plugin-auto-manager"
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
INSTALLED_PLUGINS_FILE="$CLAUDE_DIR/plugins/installed_plugins.json"
SNAPSHOT_FILE="$PLUGIN_DIR/snapshots/current.json"

echo "=========================================="
echo "Claude Plugin Auto-Manager 安装脚本"
echo "=========================================="
echo ""

# 1. 检查依赖
log_info "检查依赖..."

if ! command -v python3 &> /dev/null; then
    log_error "Python 3 未安装，请先安装 Python 3"
    exit 1
fi

if ! command -v git &> /dev/null; then
    log_error "Git 未安装，请先安装 Git"
    exit 1
fi

if [ ! -d "$CLAUDE_DIR" ]; then
    log_error "Claude Code 配置目录不存在: $CLAUDE_DIR"
    log_error "请先安装并运行 Claude Code"
    exit 1
fi

# 2. 检查插件是否已安装
if [ -f "$SETTINGS_FILE" ]; then
    if grep -q "plugin-auto-manager@local" "$SETTINGS_FILE"; then
        log_warn "插件已安装在 settings.json 中"
        read -p "是否重新安装？(y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "跳过安装"
            exit 0
        fi
    fi
fi

# 3. 设置脚本执行权限
log_info "设置脚本执行权限..."
chmod +x "$PLUGIN_DIR/scripts"/*.sh
chmod +x "$PLUGIN_DIR/scripts"/*.py

# 4. 备份配置文件
log_info "备份配置文件..."
if [ -f "$SETTINGS_FILE" ]; then
    cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup.$(date +%Y%m%d-%H%M%S)"
fi
if [ -f "$INSTALLED_PLUGINS_FILE" ]; then
    cp "$INSTALLED_PLUGINS_FILE" "$INSTALLED_PLUGINS_FILE.backup.$(date +%Y%m%d-%H%M%S)"
fi

# 5. 更新 settings.json
log_info "更新 settings.json..."

if [ -f "$SETTINGS_FILE" ]; then
    # 使用 Python 来修改 JSON（更安全）
    python3 - <<EOF
import json
from pathlib import Path

settings_file = Path("$SETTINGS_FILE")
settings = json.loads(settings_file.read_text())

# 确保 enabledPlugins 存在
if "enabledPlugins" not in settings:
    settings["enabledPlugins"] = {}

# 添加插件
settings["enabledPlugins"]["plugin-auto-manager@local"] = True

# 保存
settings_file.write_text(json.dumps(settings, indent=2) + "\n")
print("✓ 已添加到 enabledPlugins")
EOF
else
    log_error "settings.json 不存在"
    exit 1
fi

# 6. 更新 installed_plugins.json
log_info "更新 installed_plugins.json..."

if [ -f "$INSTALLED_PLUGINS_FILE" ]; then
    python3 - <<EOF
import json
from datetime import datetime, timezone
from pathlib import Path

installed_file = Path("$INSTALLED_PLUGINS_FILE")
installed = json.loads(installed_file.read_text())

# 确保 plugins 存在
if "plugins" not in installed:
    installed["plugins"] = {}

# 添加插件记录
installed["plugins"]["plugin-auto-manager@local"] = [{
    "scope": "user",
    "installPath": "$PLUGIN_DIR",
    "version": "1.0.0",
    "installedAt": datetime.now(timezone.utc).isoformat(),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}]

# 保存
installed_file.write_text(json.dumps(installed, indent=2) + "\n")
print("✓ 已添加到 installed_plugins")
EOF
else
    log_error "installed_plugins.json 不存在"
    exit 1
fi

# 7. 检查快照文件
if [ -f "$SNAPSHOT_FILE" ]; then
    log_info "发现快照文件: snapshots/current.json"

    # 读取插件数量
    PLUGIN_COUNT=$(python3 -c "import json; print(len(json.load(open('$SNAPSHOT_FILE'))['plugins']))")
    log_info "快照包含 $PLUGIN_COUNT 个插件"

    echo ""
    log_warn "下次启动 Claude Code 时，将自动安装快照中的插件"
else
    log_warn "未找到快照文件，将在首次运行时生成"
fi

# 8. 创建日志目录
mkdir -p "$PLUGIN_DIR/logs"

echo ""
echo "=========================================="
log_info "安装完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "  1. 重启 Claude Code"
echo "  2. 插件将自动运行，检查并安装缺失的插件"
echo "  3. 查看日志: tail -f $PLUGIN_DIR/logs/auto-manager.log"
echo ""
echo "配置文件: $PLUGIN_DIR/config.json"
echo "快照文件: $SNAPSHOT_FILE"
echo ""
