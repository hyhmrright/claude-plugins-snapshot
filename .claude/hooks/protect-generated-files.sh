#!/bin/bash
# PreToolUse Hook: 阻止编辑自动生成的文件
# Exit 2 = block, Exit 0 = allow

INPUT=$(cat /dev/stdin)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# 转换为相对于项目目录的路径
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
REL_PATH="${FILE_PATH#"$PROJECT_DIR"/}"

case "$REL_PATH" in
  snapshots/current.json)
    echo "此文件由 scripts/create-snapshot.py 自动生成，请运行 python3 scripts/create-snapshot.py 或 /sync" >&2
    exit 2
    ;;
  snapshots/.last-install-state.json)
    echo "此文件由 auto-manager 自动管理，不应手动编辑" >&2
    exit 2
    ;;
  hooks/hooks.json)
    echo "此文件是插件 Hook 配置，误改可能导致 Hook 失效。如确需修改请先备份" >&2
    exit 2
    ;;
esac

exit 0
