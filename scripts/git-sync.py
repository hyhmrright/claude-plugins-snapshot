#!/usr/bin/env python3
"""
同步快照到 Git 仓库
- 自动 commit 和 push 快照变更
"""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SNAPSHOT_DIR = Path.home() / ".claude" / "plugins" / "auto-manager" / "snapshots"


def log(message: str) -> None:
    """输出日志消息"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{timestamp}] {message}", flush=True)


def run_git_command(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    """执行 Git 命令"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=60, check=False
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timeout"
    except Exception as e:
        return False, str(e)


def check_git_repo() -> bool:
    """检查是否是 Git 仓库"""
    git_dir = SNAPSHOT_DIR / ".git"
    return git_dir.exists() and git_dir.is_dir()


def sync_to_git() -> bool:
    """同步到 Git"""
    if not SNAPSHOT_DIR.exists():
        log("Snapshot directory does not exist")
        return False

    if not check_git_repo():
        log("Not a Git repository, skipping sync")
        log("Run 'git init' in snapshots directory to enable Git sync")
        return False

    # 1. 检查是否有变更
    success, output = run_git_command(["git", "status", "--porcelain"], SNAPSHOT_DIR)
    if not success:
        log(f"Failed to check Git status: {output}")
        return False

    if not output.strip():
        log("No changes to commit")
        return True

    # 2. 添加所有文件
    log("Adding files to Git...")
    success, output = run_git_command(["git", "add", "."], SNAPSHOT_DIR)
    if not success:
        log(f"Failed to add files: {output}")
        return False

    # 3. 创建 commit
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    commit_msg = f"Update snapshot - {timestamp}"
    log(f"Committing: {commit_msg}")

    success, output = run_git_command(
        ["git", "commit", "-m", commit_msg], SNAPSHOT_DIR
    )
    if not success:
        log(f"Failed to commit: {output}")
        return False

    # 4. 推送到远程
    log("Pushing to remote...")
    success, output = run_git_command(["git", "push"], SNAPSHOT_DIR)
    if not success:
        # Push 失败不是致命错误，只记录日志
        log(f"Failed to push (this is not fatal): {output}")
        log("You may need to configure remote repository or check network")
        return True  # 返回 True，因为本地 commit 成功

    log("✓ Successfully synced to Git")
    return True


if __name__ == "__main__":
    try:
        success = sync_to_git()
        sys.exit(0 if success else 1)
    except Exception as e:
        log(f"Error: {e}")
        sys.exit(1)
