#!/usr/bin/env python3
"""
Claude Code 插件自动管理器
- 自动安装快照中缺失的插件
- 每 24 小时自动更新所有插件
- 发送 macOS 系统通知
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


# 配置路径
CLAUDE_DIR = Path.home() / ".claude"
AUTO_MANAGER_DIR = CLAUDE_DIR / "plugins" / "auto-manager"
SNAPSHOT_DIR = AUTO_MANAGER_DIR / "snapshots"
LOG_DIR = AUTO_MANAGER_DIR / "logs"
CONFIG_FILE = AUTO_MANAGER_DIR / "config.json"
CURRENT_SNAPSHOT = SNAPSHOT_DIR / "current.json"
LAST_UPDATE_FILE = SNAPSHOT_DIR / ".last-update"
LAST_INSTALL_STATE = SNAPSHOT_DIR / ".last-install-state.json"


def log(message: str) -> None:
    """输出日志消息"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{timestamp}] {message}", flush=True)


def load_config() -> dict:
    """加载配置文件"""
    if not CONFIG_FILE.exists():
        # 返回默认配置
        return {
            "auto_install": {"enabled": True},
            "auto_update": {"enabled": True, "interval_hours": 24, "notify": True},
            "git_sync": {"enabled": True, "auto_push": True},
            "snapshot": {"keep_versions": 10},
        }

    return json.loads(CONFIG_FILE.read_text())


def get_installed_plugins() -> set[str]:
    """获取当前已安装的插件列表"""
    installed_file = CLAUDE_DIR / "plugins" / "installed_plugins.json"
    if not installed_file.exists():
        return set()

    data = json.loads(installed_file.read_text())
    return set(data.get("plugins", {}).keys())


def get_snapshot_plugins() -> dict:
    """读取快照中的插件列表"""
    if not CURRENT_SNAPSHOT.exists():
        log("No snapshot found, skipping operations")
        return {}

    snapshot = json.loads(CURRENT_SNAPSHOT.read_text())
    return snapshot.get("plugins", {})


def load_install_state() -> set[str]:
    """加载上次安装状态（避免重复安装失败的插件）"""
    if not LAST_INSTALL_STATE.exists():
        return set()

    state = json.loads(LAST_INSTALL_STATE.read_text())
    return set(state.get("plugins", []))


def save_install_state(plugins: set[str]) -> None:
    """保存当前安装状态"""
    state = {
        "plugins": list(plugins),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    LAST_INSTALL_STATE.write_text(json.dumps(state, indent=2) + "\n")


def install_plugin(plugin_name: str, plugin_info: dict) -> bool:
    """安装单个插件"""
    try:
        # 从插件名称中提取名称和市场
        # 格式: plugin-name@marketplace-name
        parts = plugin_name.split("@")
        if len(parts) != 2:
            log(f"Invalid plugin name format: {plugin_name}")
            return False

        name, marketplace = parts
        full_name = f"{name}@{marketplace}"

        log(f"Installing {full_name}...")

        # 调用 claude plugin install
        cmd = ["claude", "plugin", "install", full_name]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
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


def check_missing_plugins() -> tuple[set[str], dict]:
    """检查缺失的插件"""
    snapshot_plugins = get_snapshot_plugins()
    if not snapshot_plugins:
        return set(), {}

    installed = get_installed_plugins()
    last_state = load_install_state()

    # 计算缺失的插件
    missing = set(snapshot_plugins.keys()) - installed

    # 过滤已尝试安装过的插件（避免反复失败）
    to_install = missing - last_state

    return to_install, snapshot_plugins


def install_missing_plugins() -> int:
    """安装缺失的插件"""
    to_install, snapshot_plugins = check_missing_plugins()

    if not to_install:
        log("All plugins from snapshot are installed")
        return 0

    log(f"Found {len(to_install)} missing plugins to install")

    # 安装缺失的插件
    installed_count = 0
    last_state = load_install_state()

    for plugin_name in to_install:
        plugin_info = snapshot_plugins[plugin_name]
        if install_plugin(plugin_name, plugin_info):
            installed_count += 1
            last_state.add(plugin_name)

    # 保存状态
    save_install_state(last_state)

    log(f"Auto-install completed: {installed_count}/{len(to_install)} successful")
    return installed_count


def should_update(config: dict) -> bool:
    """检查是否需要更新"""
    if not config["auto_update"]["enabled"]:
        log("Auto-update is disabled in config")
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
                cmd, capture_output=True, text=True, timeout=120, check=False
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
            cmd, capture_output=True, text=True, timeout=60, check=False
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


def sync_to_git(config: dict) -> bool:
    """同步快照到 Git"""
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
            cmd, capture_output=True, text=True, timeout=60, check=False
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


def send_notification(title: str, message: str) -> None:
    """发送系统通知（跨平台）"""
    import platform

    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            script = f'display notification "{message}" with title "Claude Plugins" subtitle "{title}"'
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=10,
                check=False,
            )
        elif system == "Linux":  # Linux
            # 尝试使用 notify-send
            subprocess.run(
                ["notify-send", "Claude Plugins", f"{title}: {message}"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        elif system == "Windows":  # Windows
            # 使用 PowerShell 发送通知
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $toastXml = [xml] $template.GetXml()
            $toastXml.GetElementsByTagName("text")[0].AppendChild($toastXml.CreateTextNode("Claude Plugins")) > $null
            $toastXml.GetElementsByTagName("text")[1].AppendChild($toastXml.CreateTextNode("{title}: {message}")) > $null
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
        update_count = update_all_plugins()

        if update_count > 0:
            # 发送通知
            if config["auto_update"]["notify"]:
                send_notification("Auto-Update", f"Updated {update_count} plugin(s)")

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
