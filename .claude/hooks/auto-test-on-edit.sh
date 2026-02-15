#!/bin/bash
# PostToolUse Hook: 编辑 scripts/*.py 后自动运行测试

INPUT=$(cat /dev/stdin)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
REL_PATH="${FILE_PATH#"$PROJECT_DIR"/}"

# 只对 scripts/ 下的 .py 文件触发测试
case "$REL_PATH" in
  scripts/*.py)
    cd "$PROJECT_DIR" || exit 0
    echo "--- Auto-running tests after editing $REL_PATH ---"
    uv run pytest tests/ -x -q 2>&1 | tail -20
    ;;
esac

exit 0
