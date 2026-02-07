#!/usr/bin/env bash
#
# 快照同步脚本
# 在手动安装/卸载插件后运行此脚本，生成快照并推送到 Git
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Plugin Snapshot Sync"
echo "=========================================="
echo ""

# 1. 生成快照
echo "▶ Creating snapshot..."
if python3 "$SCRIPT_DIR/create-snapshot.py"; then
    echo "✓ Snapshot created"
else
    echo "✗ Failed to create snapshot"
    exit 1
fi

echo ""

# 2. 检查是否有变化
cd "$PLUGIN_DIR"
if ! git diff --quiet snapshots/current.json; then
    echo "▶ Changes detected in snapshot"

    # 3. 提交并推送
    git add snapshots/current.json

    # 读取插件数量
    PLUGIN_COUNT=$(python3 -c "import json; print(len(json.load(open('snapshots/current.json'))['plugins']))")

    echo "▶ Committing changes..."
    git commit -m "Update plugin snapshot - $PLUGIN_COUNT plugins"

    echo "▶ Pushing to remote..."
    if git push; then
        echo ""
        echo "=========================================="
        echo "✓ Snapshot synced to GitHub successfully!"
        echo "=========================================="
        echo ""
        echo "Plugin count: $PLUGIN_COUNT"
        echo "Other machines will sync on next startup"
    else
        echo ""
        echo "⚠ Failed to push to remote"
        echo "Changes are committed locally"
    fi
else
    echo "ℹ No changes in plugin list"
    echo "Snapshot is already up to date"
fi

echo ""
