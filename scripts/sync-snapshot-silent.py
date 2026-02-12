#!/usr/bin/env python3
"""
静默版本的快照同步脚本
用于 UserPromptSubmit hook，只在有变化时才输出信息
"""
import subprocess
import sys
from pathlib import Path


def main() -> int:
    script_dir = Path(__file__).parent
    plugin_dir = script_dir.parent

    # 1. 生成快照
    result = subprocess.run(
        ["python3", str(script_dir / "create-snapshot.py")],
        cwd=plugin_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return 0  # 静默失败，不干扰用户

    # 2. 检查是否有变化
    result = subprocess.run(
        ["git", "diff", "--quiet", "snapshots/current.json"],
        cwd=plugin_dir,
        capture_output=True,
    )

    if result.returncode == 0:
        # 没有变化，静默退出
        return 0

    # 3. 有变化时，调用完整的同步脚本（会输出信息）
    result = subprocess.run(
        ["python3", str(script_dir / "sync-snapshot.py")],
        cwd=plugin_dir,
    )
    return result.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # 静默失败
