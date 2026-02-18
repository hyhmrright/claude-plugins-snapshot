#!/usr/bin/env bash
#
# SessionStart Hook 入口脚本
# 由 Claude Code 的 async: true 配置负责后台化执行
#

set -euo pipefail

# 获取插件根目录
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/auto-manager}"
LOG_FILE="$PLUGIN_ROOT/logs/auto-manager.log"

# 确保日志目录存在
mkdir -p "$(dirname "$LOG_FILE")"

# 清除嵌套会话检测环境变量，允许执行 claude 子命令
unset CLAUDECODE CLAUDE_CODE_SESSION_ID

echo "========================================" >> "$LOG_FILE" 2>&1
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] SessionStart triggered" >> "$LOG_FILE" 2>&1

# 等待 Claude Code 完成初始化（避免竞态条件导致 plugin update 失败）
sleep 10

# 直接同步执行（async: true 由 Claude Code hook 配置负责后台化）
python3 "$PLUGIN_ROOT/scripts/auto-manager.py" >> "$LOG_FILE" 2>&1
