#!/usr/bin/env python3
"""
快照同步脚本（跨平台）
在手动安装/卸载插件后运行此脚本，生成快照并推送到 Git
"""
import json
import subprocess
import sys
from pathlib import Path


def log_info(msg: str) -> None:
    print(f"✓ {msg}")


def log_error(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)


def run_command(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    """运行命令"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=60, check=False
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def main() -> int:
    print("=" * 50)
    print("Plugin Snapshot Sync")
    print("=" * 50)
    print()

    # 获取目录
    script_dir = Path(__file__).parent
    plugin_dir = script_dir.parent

    # 1. 生成快照
    print("▶ Creating snapshot...")
    success, output = run_command(
        ["python3", str(script_dir / "create-snapshot.py")], plugin_dir
    )
    if not success:
        log_error(f"Failed to create snapshot: {output}")
        return 1
    log_info("Snapshot created")
    print()

    # 2. 检查是否有变化
    success, _ = run_command(
        ["git", "diff", "--quiet", "snapshots/current.json"], plugin_dir
    )

    if success:
        # 没有变化
        print("ℹ No changes in plugin list")
        print("Snapshot is already up to date")
        return 0

    print("▶ Changes detected in snapshot")

    # 3. 读取插件数量
    try:
        snapshot_file = plugin_dir / "snapshots" / "current.json"
        snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
        plugin_count = len(snapshot.get("plugins", {}))
    except Exception as e:
        log_error(f"Failed to read snapshot: {e}")
        return 1

    # 4. 提交
    print("▶ Committing changes...")
    run_command(["git", "add", "snapshots/current.json"], plugin_dir)

    commit_msg = f"Update plugin snapshot - {plugin_count} plugins"
    success, output = run_command(["git", "commit", "-m", commit_msg], plugin_dir)
    if not success:
        log_error(f"Failed to commit: {output}")
        return 1

    # 5. 推送
    print("▶ Pushing to remote...")
    success, output = run_command(["git", "push"], plugin_dir)

    print()
    print("=" * 50)
    if success:
        log_info("Snapshot synced to GitHub successfully!")
    else:
        print("⚠ Failed to push to remote")
        print("Changes are committed locally")
        print(f"Error: {output}")
    print("=" * 50)
    print()
    print(f"Plugin count: {plugin_count}")
    print("Other machines will sync on next startup")
    print()

    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nCancelled")
        sys.exit(1)
    except Exception as e:
        log_error(f"Error: {e}")
        sys.exit(1)
