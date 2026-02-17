#!/usr/bin/env bash
#
# SessionStart Hook 入口脚本
# 在后台执行 auto-manager.py，避免阻塞 Claude 启动
#

set -euo pipefail

# 获取插件根目录
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/auto-manager}"
LOG_FILE="$PLUGIN_ROOT/logs/auto-manager.log"

# 确保日志目录存在
mkdir -p "$(dirname "$LOG_FILE")"

# 清除嵌套会话检测环境变量，允许后台进程执行 claude 子命令
unset CLAUDECODE CLAUDE_CODE_SESSION_ID

# 在后台执行自动管理器，使用 nohup + disown 防止 SIGHUP 杀掉后台进程
(
  echo "========================================" >> "$LOG_FILE" 2>&1
  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] SessionStart triggered" >> "$LOG_FILE" 2>&1
  nohup python3 "$PLUGIN_ROOT/scripts/auto-manager.py" >> "$LOG_FILE" 2>&1
) &
disown

# 立即返回，不阻塞会话启动
exit 0
