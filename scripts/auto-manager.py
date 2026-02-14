#!/usr/bin/env python3
"""
Claude Code 插件自动管理器
- 自动安装快照中缺失的插件
- 每 24 小时自动更新所有插件
- 发送 macOS 系统通知
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Set, Tuple


# 配置路径
CLAUDE_DIR = Path.home() / ".claude"
AUTO_MANAGER_DIR = CLAUDE_DIR / "plugins" / "auto-manager"
SNAPSHOT_DIR = AUTO_MANAGER_DIR / "snapshots"
LOG_DIR = AUTO_MANAGER_DIR / "logs"
CONFIG_FILE = AUTO_MANAGER_DIR / "config.json"
CURRENT_SNAPSHOT = SNAPSHOT_DIR / "current.json"
LAST_UPDATE_FILE = SNAPSHOT_DIR / ".last-update"
LAST_INSTALL_STATE = SNAPSHOT_DIR / ".last-install-state.json"

# 常量配置
# 日志管理
MAX_LOG_SIZE_MB = 10
KEEP_LOG_SIZE_MB = 8

# 重试机制
RETRY_INTERVAL_SECONDS = 600  # 10 分钟
MAX_RETRY_COUNT = 5

# 超时时间（秒）
COMMAND_TIMEOUT_SHORT = 60   # Git 操作、快照创建
COMMAND_TIMEOUT_LONG = 120   # 插件安装/更新


def log(message: str) -> None:
    """输出日志消息，并管理日志文件大小（限制 10MB）"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{timestamp}] {message}", flush=True)

    # 日志轮转：如果超过限制则截断（错误不影响主流程）
    try:
        max_size = MAX_LOG_SIZE_MB * 1024 * 1024
        log_file = LOG_DIR / "auto-manager.log"

        if log_file.exists() and log_file.stat().st_size > max_size:
            # 读取最后保留的内容
            keep_size = KEEP_LOG_SIZE_MB * 1024 * 1024
            file_size = log_file.stat().st_size

            # 计算 seek 位置，避免超出文件大小
            seek_offset = max(-file_size, -keep_size)

            with open(log_file, "rb") as f:
                f.seek(seek_offset, 2)  # 从文件末尾往前
                content = f.read()

            # 找到第一个完整行的开始位置
            first_newline = content.find(b"\n")
            if first_newline != -1:
                content = content[first_newline + 1:]

            # 写回截断后的内容（使用临时文件避免损坏）
            temp_log = log_file.with_suffix(".log.tmp")
            with open(temp_log, "wb") as f:
                f.write(f"[{timestamp}] [LOG ROTATED - keeping last {KEEP_LOG_SIZE_MB}MB]\n".encode())
                f.write(content)
            temp_log.rename(log_file)
    except Exception as e:
        # 日志轮转失败不影响主流程，输出到 stderr
        print(f"[{timestamp}] Warning: Log rotation failed: {e}", file=sys.stderr, flush=True)


def load_config() -> Dict[str, Any]:
    """加载配置文件

    Returns:
        Dict[str, Any]: 配置字典，包含 auto_install, auto_update, git_sync, snapshot 等配置项
    """
    if not CONFIG_FILE.exists():
        # 返回默认配置
        return {
            "auto_install": {"enabled": True},
            "auto_update": {"enabled": True, "interval_hours": 24, "notify": True},
            "git_sync": {"enabled": True, "auto_push": True},
            "snapshot": {"keep_versions": 10},
        }

    return json.loads(CONFIG_FILE.read_text())


def get_installed_plugins() -> Set[str]:
    """获取当前已安装的插件列表

    Returns:
        Set[str]: 已安装插件名称集合（格式：plugin-name@marketplace）
    """
    installed_file = CLAUDE_DIR / "plugins" / "installed_plugins.json"
    if not installed_file.exists():
        return set()

    data = json.loads(installed_file.read_text())
    return set(data.get("plugins", {}).keys())


def get_snapshot_plugins() -> Dict[str, Any]:
    """读取快照中的插件列表

    Returns:
        Dict[str, Any]: 快照中的插件字典，键为插件名，值为插件配置信息
    """
    if not CURRENT_SNAPSHOT.exists():
        log("No snapshot found, skipping operations")
        return {}

    snapshot = json.loads(CURRENT_SNAPSHOT.read_text())
    return snapshot.get("plugins", {})


def load_install_state() -> Dict[str, Any]:
    """加载安装状态（支持重试机制）

    返回格式:
    {
        "plugin-name@marketplace": {
            "status": "installed" | "failed",
            "last_attempt": "ISO8601 timestamp",
            "retry_count": 0-5,
            "first_failed_at": "ISO8601 timestamp"  # 仅在失败时存在
        }
    }
    """
    if not LAST_INSTALL_STATE.exists():
        return {}

    state_data = json.loads(LAST_INSTALL_STATE.read_text())

    # 兼容旧格式（简单的 plugins 列表）
    if "plugins" in state_data and isinstance(state_data["plugins"], list):
        # 转换为新格式
        return {
            plugin: {"status": "installed", "last_attempt": state_data.get("timestamp", ""), "retry_count": 0}
            for plugin in state_data["plugins"]
        }

    # 返回新格式
    return state_data.get("plugins", {})


def save_install_state(state: Dict[str, Any]) -> None:
    """保存安装状态（使用原子写入防止文件损坏）

    参数:
        state: 插件状态字典，格式见 load_install_state()
    """
    state_data = {
        "plugins": state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 使用临时文件 + rename 实现原子写入（Unix 系统保证原子性）
    temp_file = LAST_INSTALL_STATE.with_suffix(".json.tmp")
    temp_file.write_text(json.dumps(state_data, indent=2) + "\n")
    temp_file.rename(LAST_INSTALL_STATE)


def install_plugin(plugin_name: str, plugin_info: Dict[str, Any]) -> bool:
    """安装单个插件

    Args:
        plugin_name: 插件名称（格式：plugin-name@marketplace）
        plugin_info: 插件配置信息字典

    Returns:
        bool: 安装成功返回 True，失败返回 False
    """
    try:
        # 从插件名称中提取名称和市场
        # 格式: plugin-name@marketplace-name
        parts = plugin_name.split("@")
        if len(parts) != 2:
            log(f"✗ Invalid plugin name format (expected 'name@marketplace'): {plugin_name}")
            return False

        name, marketplace = parts

        # 验证名称和市场非空
        if not name or not marketplace:
            log(f"✗ Empty plugin name or marketplace: {plugin_name}")
            return False

        full_name = f"{name}@{marketplace}"

        log(f"Installing {full_name}...")

        # 调用 claude plugin install
        cmd = ["claude", "plugin", "install", full_name]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_LONG, check=False
        )

        if result.returncode == 0:
            log(f"✓ Installed {full_name}")
            return True
        else:
            log(f"✗ Failed to install {full_name}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log(f"✗ Timeout installing {plugin_name}")
        return False
    except Exception as e:
        log(f"✗ Error installing {plugin_name}: {e}")
        return False


def check_missing_plugins() -> Tuple[Set[str], Dict[str, Any]]:
    """检查缺失的插件，支持失败重试

    重试策略:
    - 失败后 10 分钟才能重试
    - 最多重试 5 次
    - 5 次失败后放弃，等待手动更新

    Returns:
        Tuple[Set[str], Dict[str, Any]]: (需要安装的插件集合, 快照中的所有插件字典)
    """
    snapshot_plugins = get_snapshot_plugins()
    if not snapshot_plugins:
        return set(), {}

    installed = get_installed_plugins()
    state = load_install_state()

    # 计算缺失的插件
    missing = set(snapshot_plugins.keys()) - installed

    # 过滤需要安装的插件
    to_install = set()
    now = datetime.now(timezone.utc)

    for plugin in missing:
        if plugin not in state:
            # 新的缺失插件，需要安装
            to_install.add(plugin)
        else:
            plugin_state = state[plugin]
            status = plugin_state.get("status")
            retry_count = plugin_state.get("retry_count", 0)

            if status == "installed":
                # 已安装但现在缺失，重新安装
                to_install.add(plugin)
            elif status == "failed":
                # 检查是否可以重试
                if retry_count > MAX_RETRY_COUNT:
                    # 超过最大重试次数，跳过
                    log(f"Skipping {plugin}: exceeded max retries ({MAX_RETRY_COUNT})")
                    continue

                # 检查距离上次尝试是否超过 10 分钟
                last_attempt_str = plugin_state.get("last_attempt", "")
                try:
                    last_attempt = datetime.fromisoformat(last_attempt_str)
                    # 确保时区感知（兼容旧数据）
                    if last_attempt.tzinfo is None:
                        last_attempt = last_attempt.replace(tzinfo=timezone.utc)
                    elapsed = (now - last_attempt).total_seconds()

                    if elapsed >= RETRY_INTERVAL_SECONDS:
                        log(f"Retrying {plugin}: {elapsed/60:.1f} minutes since last attempt (retry {retry_count + 1}/{MAX_RETRY_COUNT})")
                        to_install.add(plugin)
                    else:
                        log(f"Skipping {plugin}: only {elapsed/60:.1f} minutes since last attempt (need 10)")
                except (ValueError, TypeError):
                    # 时间戳解析失败，允许重试
                    to_install.add(plugin)

    return to_install, snapshot_plugins


def install_missing_plugins() -> int:
    """安装缺失的插件，并记录失败重试信息

    Returns:
        int: 成功安装的插件数量
    """
    to_install, snapshot_plugins = check_missing_plugins()

    if not to_install:
        log("All plugins from snapshot are installed")
        return 0

    log(f"Found {len(to_install)} missing plugins to install")

    # 加载当前状态
    state = load_install_state()
    installed_count = 0
    now = datetime.now(timezone.utc).isoformat()

    for plugin_name in to_install:
        plugin_info = snapshot_plugins[plugin_name]
        success = install_plugin(plugin_name, plugin_info)

        if success:
            # 安装成功
            installed_count += 1
            state[plugin_name] = {
                "status": "installed",
                "last_attempt": now,
                "retry_count": 0,
            }
        else:
            # 安装失败，更新重试信息
            if plugin_name in state and state[plugin_name].get("status") == "failed":
                # 已经失败过，增加重试计数
                state[plugin_name]["retry_count"] = state[plugin_name].get("retry_count", 1) + 1
                state[plugin_name]["last_attempt"] = now
            else:
                # 首次失败（retry_count=1 表示首次失败）
                state[plugin_name] = {
                    "status": "failed",
                    "last_attempt": now,
                    "retry_count": 1,
                    "first_failed_at": now,
                }

    # 保存状态
    save_install_state(state)

    log(f"Auto-install completed: {installed_count}/{len(to_install)} successful")
    return installed_count


def is_in_claude_session() -> bool:
    """检测是否在 Claude Code 会话中运行"""
    return "CLAUDE_CODE_SESSION_ID" in os.environ


def should_update(config: Dict[str, Any]) -> bool:
    """检查是否需要更新

    Args:
        config: 配置字典

    Returns:
        bool: 需要更新返回 True，否则返回 False
    """
    if not config["auto_update"]["enabled"]:
        log("Auto-update is disabled in config")
        return False

    # 检测是否在 Claude Code 会话中
    if is_in_claude_session():
        log("Running inside Claude Code session, skipping plugin update to avoid nested session error")
        return False

    interval_hours = config["auto_update"]["interval_hours"]

    # 如果 interval_hours=0，每次启动都更新
    if interval_hours == 0:
        log("Update interval set to 0, triggering update on every launch")
        return True

    if not LAST_UPDATE_FILE.exists():
        log("No previous update timestamp, triggering update")
        return True

    # 读取上次更新时间
    last_update_str = LAST_UPDATE_FILE.read_text().strip()
    try:
        last_update = datetime.fromisoformat(last_update_str)
    except ValueError:
        log("Invalid last update timestamp, triggering update")
        return True

    # 计算时间差
    now = datetime.now(timezone.utc)
    delta = now - last_update

    if delta >= timedelta(hours=interval_hours):
        log(
            f"Last update was {delta.total_seconds() / 3600:.1f} hours ago, triggering update"
        )
        return True

    log(f"Last update was {delta.total_seconds() / 3600:.1f} hours ago, skipping")
    return False


def update_all_marketplaces() -> int:
    """更新所有 Marketplaces"""
    try:
        log("Updating all marketplaces...")
        cmd = ["claude", "plugin", "marketplace", "update"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_LONG, check=False
        )

        if result.returncode == 0:
            log("✓ All marketplaces updated")
            return 1
        else:
            log(f"✗ Failed to update marketplaces: {result.stderr}")
            return 0
    except subprocess.TimeoutExpired:
        log("✗ Timeout updating marketplaces")
        return 0
    except Exception as e:
        log(f"✗ Error updating marketplaces: {e}")
        return 0


def update_all_plugins() -> int:
    """更新所有已安装的插件"""
    installed = get_installed_plugins()

    if not installed:
        log("No plugins installed, skipping update")
        return 0

    log(f"Updating {len(installed)} plugins...")

    update_count = 0
    fail_count = 0

    for plugin_name in installed:
        try:
            log(f"Updating {plugin_name}...")
            cmd = ["claude", "plugin", "update", plugin_name]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_LONG, check=False
            )

            if result.returncode == 0:
                log(f"✓ Updated {plugin_name}")
                update_count += 1
            else:
                log(f"✗ Failed to update {plugin_name}: {result.stderr}")
                fail_count += 1
        except subprocess.TimeoutExpired:
            log(f"✗ Timeout updating {plugin_name}")
            fail_count += 1
        except Exception as e:
            log(f"✗ Error updating {plugin_name}: {e}")
            fail_count += 1

    log(f"Update completed: {update_count} updated, {fail_count} failed")
    return update_count


def update_timestamp() -> None:
    """更新时间戳"""
    timestamp = datetime.now(timezone.utc).isoformat()
    LAST_UPDATE_FILE.write_text(timestamp + "\n")
    log(f"Updated timestamp: {timestamp}")


def snapshot_has_changes() -> bool:
    """检查快照是否有实质性变化（插件列表变化）"""
    if not CURRENT_SNAPSHOT.exists():
        return True  # 没有快照，肯定有变化

    try:
        # 读取当前快照
        old_snapshot = json.loads(CURRENT_SNAPSHOT.read_text())
        old_plugins = set(old_snapshot.get("plugins", {}).keys())

        # 获取当前已安装插件
        current_plugins = get_installed_plugins()

        # 比较插件列表
        if old_plugins != current_plugins:
            added = current_plugins - old_plugins
            removed = old_plugins - current_plugins
            if added:
                log(f"New plugins detected: {', '.join(added)}")
            if removed:
                log(f"Removed plugins detected: {', '.join(removed)}")
            return True

        log("Plugin list unchanged, no need to sync to Git")
        return False
    except Exception as e:
        log(f"Error checking snapshot changes: {e}")
        return True  # 出错时保守处理，认为有变化


def create_new_snapshot() -> bool:
    """创建新快照"""
    try:
        log("Creating new snapshot...")
        cmd = [
            "python3",
            str(AUTO_MANAGER_DIR / "scripts" / "create-snapshot.py"),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SHORT, check=False
        )

        if result.returncode == 0:
            log("✓ Snapshot created")
            return True
        else:
            log(f"✗ Failed to create snapshot: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ Error creating snapshot: {e}")
        return False


def sync_to_git(config: Dict[str, Any]) -> bool:
    """同步快照到 Git

    Args:
        config: 配置字典

    Returns:
        bool: 同步成功返回 True，失败返回 False
    """
    if not config["git_sync"]["enabled"]:
        log("Git sync is disabled in config")
        return False

    try:
        log("Syncing to Git...")
        cmd = [
            "python3",
            str(AUTO_MANAGER_DIR / "scripts" / "git-sync.py"),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SHORT, check=False
        )

        if result.returncode == 0:
            log("✓ Git sync completed")
            return True
        else:
            log(f"✗ Failed to sync to Git: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ Error syncing to Git: {e}")
        return False


def cleanup_claude_backups() -> None:
    """清理 Claude Code 自动生成的带时间戳的备份文件

    只删除 ~/.claude.json.backup.<timestamp> 格式的文件
    保留 ~/.claude.json.backup（主备份文件）
    """
    try:
        claude_json = CLAUDE_DIR / ".claude.json"
        parent_dir = claude_json.parent

        # 查找所有 .claude.json.backup.* 文件
        backup_files = list(parent_dir.glob(".claude.json.backup.*"))

        if not backup_files:
            log("No timestamped backup files to clean up")
            return

        log(f"Found {len(backup_files)} timestamped backup files to clean up")

        # 删除所有带时间戳的备份文件
        deleted_count = 0
        for backup_file in backup_files:
            try:
                backup_file.unlink()
                log(f"Deleted: {backup_file.name}")
                deleted_count += 1
            except Exception as e:
                log(f"Failed to delete {backup_file.name}: {e}")

        if deleted_count > 0:
            log(f"✓ Cleaned up {deleted_count} backup file(s)")
    except Exception as e:
        log(f"Error during backup cleanup: {e}")


def send_notification(title: str, message: str) -> None:
    """发送系统通知（跨平台）"""
    import platform

    system = platform.system()

    # 转义特殊字符防止命令注入
    def escape_for_applescript(text: str) -> str:
        """转义 AppleScript 字符串中的特殊字符"""
        return text.replace('\\', '\\\\').replace('"', '\\"')

    def escape_for_powershell(text: str) -> str:
        """转义 PowerShell 字符串中的特殊字符"""
        return text.replace('"', '`"').replace('$', '`$')

    try:
        if system == "Darwin":  # macOS
            safe_title = escape_for_applescript(title)
            safe_message = escape_for_applescript(message)
            script = f'display notification "{safe_message}" with title "Claude Plugins" subtitle "{safe_title}"'
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=10,
                check=False,
            )
        elif system == "Linux":  # Linux
            # notify-send 自动处理特殊字符
            subprocess.run(
                ["notify-send", "Claude Plugins", f"{title}: {message}"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        elif system == "Windows":  # Windows
            # 使用 PowerShell 发送通知
            safe_title = escape_for_powershell(title)
            safe_message = escape_for_powershell(message)
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $toastXml = [xml] $template.GetXml()
            $toastXml.GetElementsByTagName("text")[0].AppendChild($toastXml.CreateTextNode("Claude Plugins")) | Out-Null
            $toastXml.GetElementsByTagName("text")[1].AppendChild($toastXml.CreateTextNode("{safe_title}: {safe_message}")) | Out-Null
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($toastXml.OuterXml)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Plugins").Show($toast)
            """
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                timeout=10,
                check=False,
            )
        else:
            log(f"Notifications not supported on {system}")
            return

        log(f"Notification sent: {title} - {message}")
    except FileNotFoundError:
        log(f"Notification command not found on {system}")
    except Exception as e:
        log(f"Failed to send notification: {e}")


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description="Claude Code Plugin Auto Manager")
    parser.add_argument(
        "--force-update", action="store_true", help="Force update regardless of timestamp"
    )
    args = parser.parse_args()

    log("========================================")
    log("Claude Plugin Auto-Manager Started")
    log("========================================")

    # 清理 Claude Code 自动生成的备份文件
    cleanup_claude_backups()

    # 加载配置
    config = load_config()

    # 检查安装前的插件列表变化
    plugins_changed = False

    # 1. 安装缺失的插件
    if config["auto_install"]["enabled"]:
        installed_count = install_missing_plugins()
        if installed_count > 0:
            plugins_changed = True  # 安装了新插件，需要同步
            if config["auto_update"]["notify"]:
                send_notification(
                    "Auto-Install", f"Installed {installed_count} missing plugin(s)"
                )
    else:
        log("Auto-install is disabled in config")

    # 2. 检查是否需要更新
    if args.force_update or should_update(config):
        # 先更新 marketplaces
        marketplace_updated = update_all_marketplaces()

        # 再更新插件
        update_count = update_all_plugins()

        if marketplace_updated > 0 or update_count > 0:
            # 发送通知
            if config["auto_update"]["notify"]:
                msg = f"Updated {update_count} plugin(s)"
                if marketplace_updated > 0:
                    msg = f"Updated marketplaces and {update_count} plugin(s)"
                send_notification("Auto-Update", msg)

        # 更新时间戳
        update_timestamp()

    # 3. 只在插件列表变化时才创建快照并同步到 Git
    if plugins_changed or snapshot_has_changes():
        log("Plugin list changed, creating snapshot and syncing to Git...")

        # 创建新快照
        create_new_snapshot()

        # 同步到 Git
        if sync_to_git(config):
            log("✓ Snapshot synced to Git")
    else:
        log("No plugin list changes, skipping Git sync")

    log("========================================")
    log("Claude Plugin Auto-Manager Finished")
    log("========================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Fatal error: {e}")
        sys.exit(1)
