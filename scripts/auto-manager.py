#!/usr/bin/env python3
"""
Claude Code 插件自动管理器
- 自动安装快照中缺失的插件
- 每 24 小时自动更新所有插件
- 发送 macOS 系统通知
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


# 配置路径
CLAUDE_DIR = Path.home() / ".claude"
AUTO_MANAGER_DIR = CLAUDE_DIR / "plugins" / "auto-manager"
SNAPSHOT_DIR = AUTO_MANAGER_DIR / "snapshots"
LOG_DIR = AUTO_MANAGER_DIR / "logs"
CONFIG_FILE = AUTO_MANAGER_DIR / "config.json"
CURRENT_SNAPSHOT = SNAPSHOT_DIR / "current.json"
LAST_UPDATE_FILE = SNAPSHOT_DIR / ".last-update"
LAST_INSTALL_STATE = SNAPSHOT_DIR / ".last-install-state.json"
GLOBAL_RULES_SOURCE = AUTO_MANAGER_DIR / "global-rules" / "CLAUDE.md"
GLOBAL_RULES_TARGET = CLAUDE_DIR / "CLAUDE.md"
GLOBAL_SKILLS_SOURCE_DIR = AUTO_MANAGER_DIR / "global-skills"
GLOBAL_SKILLS_TARGET_DIR = CLAUDE_DIR / "skills"
KNOWN_MARKETPLACES_FILE = CLAUDE_DIR / "plugins" / "known_marketplaces.json"
GLOBAL_SETTINGS_LOCAL = CLAUDE_DIR / "settings.local.json"
SESSION_START_SCRIPT = AUTO_MANAGER_DIR / "scripts" / "session-start.sh"
STARTUP_SERVICE_SCRIPT = AUTO_MANAGER_DIR / "scripts" / "startup-service.py"

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
HOOK_TIMEOUT = 120           # SessionStart Hook 超时

# 双重运行防护：5 分钟内运行过则跳过（防 OS 服务 + Claude Code Hook 同时触发）
RECENT_RUN_THRESHOLD_SECONDS = 300


def log(message: str) -> None:
    """输出日志消息，并在日志文件超过限制时自动轮转"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{timestamp}] {message}", flush=True)

    # 日志轮转（错误不影响主流程）
    try:
        max_size = MAX_LOG_SIZE_MB * 1024 * 1024
        log_file = LOG_DIR / "auto-manager.log"

        if log_file.exists() and log_file.stat().st_size > max_size:
            keep_size = KEEP_LOG_SIZE_MB * 1024 * 1024
            file_size = log_file.stat().st_size
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
    """加载配置文件，不存在时返回默认配置"""
    if not CONFIG_FILE.exists():
        # 返回默认配置
        return {
            "auto_install": {"enabled": True},
            "auto_update": {"enabled": True, "interval_hours": 24, "notify": True},
            "git_sync": {"enabled": True, "auto_push": True},
            "global_sync": {"enabled": True},
            "global_skills_sync": {"enabled": True},
            "snapshot": {"keep_versions": 10},
        }

    return json.loads(CONFIG_FILE.read_text())


def get_installed_plugins() -> Set[str]:
    """获取当前已安装的插件名称集合（格式：name@marketplace）"""
    installed_file = CLAUDE_DIR / "plugins" / "installed_plugins.json"
    if not installed_file.exists():
        return set()

    data = json.loads(installed_file.read_text())
    return set(data.get("plugins", {}).keys())


def get_snapshot_plugins() -> Dict[str, Any]:
    """读取快照中的插件字典"""
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
    """安装单个插件，返回是否成功"""
    try:
        # 验证插件名称格式: name@marketplace
        parts = plugin_name.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            log(f"✗ Invalid plugin name format (expected 'name@marketplace'): {plugin_name}")
            return False

        log(f"Installing {plugin_name}...")

        cmd = ["claude", "plugin", "install", plugin_name]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_LONG, check=False
        )

        if result.returncode == 0:
            log(f"✓ Installed {plugin_name}")
            return True

        log(f"✗ Failed to install {plugin_name}: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        log(f"✗ Timeout installing {plugin_name}")
        return False
    except Exception as e:
        log(f"✗ Error installing {plugin_name}: {e}")
        return False


def check_missing_plugins() -> Tuple[Set[str], Dict[str, Any]]:
    """检查缺失的插件，返回 (需要安装的插件集合, 快照插件字典)

    重试策略: 失败后等待 RETRY_INTERVAL_SECONDS 重试，最多 MAX_RETRY_COUNT 次
    """
    snapshot_plugins = get_snapshot_plugins()
    if not snapshot_plugins:
        return set(), {}

    installed = get_installed_plugins()
    state = load_install_state()

    # 计算缺失的插件（排除本地插件，它们通过 ensure_self_registered() 管理）
    all_missing = set(snapshot_plugins.keys()) - installed
    missing = {plugin for plugin in all_missing if "@" in plugin}
    local_count = len(all_missing) - len(missing)
    if local_count > 0:
        log(f"Skipping {local_count} local plugin(s) (no @marketplace suffix)")

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
    """安装缺失的插件并记录重试状态，返回成功安装数量"""
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
    """检测是否在 Claude Code 会话中运行

    claude CLI 使用 CLAUDECODE 环境变量检测嵌套会话。
    session-start.sh 在启动后台进程前会 unset 这些变量，
    所以正常的 Hook 触发不会命中此检测。
    """
    return "CLAUDECODE" in os.environ


def should_update(config: Dict[str, Any]) -> bool:
    """根据配置和上次更新时间判断是否需要更新"""
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


def _is_valid_marketplace_name(name: str) -> bool:
    """验证 marketplace 名称格式（仅允许字母、数字、连字符、下划线）"""
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))


def get_all_marketplaces() -> List[str]:
    """读取所有已知的 marketplace 名称列表

    从 ~/.claude/plugins/known_marketplaces.json 读取。
    文件不存在或读取失败时返回空列表。
    名称格式无效的 marketplace 会被跳过。
    """
    if not KNOWN_MARKETPLACES_FILE.exists():
        log(f"Known marketplaces file not found: {KNOWN_MARKETPLACES_FILE}")
        return []

    try:
        data = json.loads(KNOWN_MARKETPLACES_FILE.read_text())
        names: List[str] = []
        invalid: List[str] = []
        for k in data:
            if _is_valid_marketplace_name(k):
                names.append(k)
            else:
                invalid.append(k)
        if invalid:
            log(f"Skipping invalid marketplace names: {', '.join(invalid)}")
        log(f"Found {len(names)} marketplace(s): {', '.join(names)}")
        return names
    except Exception as e:
        log(f"Error reading known marketplaces: {e}")
        return []


def _update_single_marketplace(name: str) -> bool:
    """更新单个 marketplace，返回是否成功

    参数:
        name: marketplace 名称，传入空字符串时执行无参数的默认更新命令
    """
    label = name if name else "default"
    cmd = ["claude", "plugin", "marketplace", "update"]
    if name:
        cmd.append(name)

    try:
        log(f"Updating marketplace: {label}...")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_LONG, check=False
        )

        if result.returncode == 0:
            log(f"✓ Updated marketplace: {label}")
            return True

        log(f"✗ Failed to update marketplace {label}: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        log(f"✗ Timeout updating marketplace: {label}")
        return False
    except Exception as e:
        log(f"✗ Error updating marketplace {label}: {e}")
        return False


def update_all_marketplaces() -> int:
    """逐个更新所有 Marketplaces，返回成功更新的数量

    读取 known_marketplaces.json 获取所有 marketplace 名称，
    逐个执行 `claude plugin marketplace update <name>`。
    如果读取失败，回退到无参数命令（只更新官方 marketplace）。
    """
    marketplaces = get_all_marketplaces()

    if not marketplaces:
        log("No marketplaces found, falling back to default update command")
        return 1 if _update_single_marketplace("") else 0

    log(f"Updating {len(marketplaces)} marketplace(s)...")
    success_count = sum(1 for name in marketplaces if _update_single_marketplace(name))
    log(f"Marketplace update completed: {success_count}/{len(marketplaces)} successful")
    return success_count


def _update_single_plugin(plugin_name: str) -> bool:
    """更新单个插件，返回是否成功

    如果使用完整名称（name@marketplace）更新失败且错误为 "not installed"，
    会自动使用基础名称（name）重试。

    参数:
        plugin_name: 插件名称（格式: name@marketplace）
    """
    try:
        log(f"Updating {plugin_name}...")
        cmd = ["claude", "plugin", "update", plugin_name]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_LONG, check=False
        )

        # 如果完整名称找不到，尝试使用基础名称重试
        # 检查 stdout + stderr，因为 claude CLI 可能将错误输出到任一流
        combined_output = (result.stdout + result.stderr).lower()
        if result.returncode != 0 and "not installed" in combined_output:
            base_name = plugin_name.split("@")[0]
            log(f"Retrying with base name: {base_name}...")
            cmd = ["claude", "plugin", "update", base_name]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_LONG, check=False
            )

        if result.returncode == 0:
            log(f"✓ Updated {plugin_name}")
            return True

        error_msg = result.stderr.strip() or result.stdout.strip()
        log(f"✗ Failed to update {plugin_name}: {error_msg}")
        return False
    except subprocess.TimeoutExpired:
        log(f"✗ Timeout updating {plugin_name}")
        return False
    except Exception as e:
        log(f"✗ Error updating {plugin_name}: {e}")
        return False


def is_plugin_management_available() -> bool:
    """检查 claude plugin 命令是否可用

    某些 Claude Code 版本中，versioned plugins 功能可能被服务端
    feature flag (tengu_enable_versioned_plugins) 禁用，导致
    claude plugin list/update 等命令无法正常工作。

    通过对比 CLI 输出与 installed_plugins.json 来检测此情况：
    若 CLI 报告无插件但 JSON 中有插件，说明功能被禁用。
    """
    installed = get_installed_plugins()
    if not installed:
        return True  # 无已安装插件，无法判断，允许尝试

    try:
        result = subprocess.run(
            ["claude", "plugin", "list"],
            capture_output=True, text=True, timeout=30, check=False
        )
        combined = (result.stdout + result.stderr).lower()
        if "no plugins installed" in combined:
            log(
                "⚠ Plugin update unavailable: versioned plugins feature flag is disabled "
                "(tengu_enable_versioned_plugins=false). "
                "Plugin management commands will be skipped until the flag is re-enabled."
            )
            return False
    except Exception:
        pass  # 检查失败时不阻止更新尝试

    return True


def update_all_plugins() -> int:
    """更新所有已安装的插件（跳过本地插件）"""
    installed = get_installed_plugins()

    if not installed:
        log("No plugins installed, skipping update")
        return 0

    if not is_plugin_management_available():
        return 0

    # 过滤掉本地插件（无 @ 标识的插件）
    remote_plugins = [name for name in installed if "@" in name]
    skipped = len(installed) - len(remote_plugins)
    if skipped:
        log(f"Skipping {skipped} local plugin(s)")

    if not remote_plugins:
        log("No remote plugins to update")
        return 0

    log(f"Updating {len(remote_plugins)} plugin(s)...")
    success_count = sum(1 for name in remote_plugins if _update_single_plugin(name))
    fail_count = len(remote_plugins) - success_count
    log(f"Update completed: {success_count} updated, {fail_count} failed")
    return success_count


def update_timestamp() -> None:
    """更新时间戳"""
    timestamp = datetime.now(timezone.utc).isoformat()
    LAST_UPDATE_FILE.write_text(timestamp + "\n")
    log(f"Updated timestamp: {timestamp}")


def get_local_marketplaces() -> Set[str]:
    """获取本地已知 marketplace 名称集合"""
    if not KNOWN_MARKETPLACES_FILE.exists():
        return set()
    try:
        data = json.loads(KNOWN_MARKETPLACES_FILE.read_text())
        return set(data.keys())
    except Exception:
        return set()


def snapshot_has_changes() -> bool:
    """检查快照是否有实质性变化（插件列表或 marketplace 列表变化）"""
    if not CURRENT_SNAPSHOT.exists():
        return True  # 没有快照，肯定有变化

    try:
        old_snapshot = json.loads(CURRENT_SNAPSHOT.read_text())
        old_plugins = set(old_snapshot.get("plugins", {}).keys())
        old_marketplaces = set(old_snapshot.get("marketplaces", {}).keys())

        # 过滤掉本地插件（无 @ 后缀），与快照中的插件列表保持一致
        current_plugins = {p for p in get_installed_plugins() if "@" in p}
        current_marketplaces = get_local_marketplaces()

        changed = False

        if old_plugins != current_plugins:
            added = current_plugins - old_plugins
            removed = old_plugins - current_plugins
            if added:
                log(f"New plugins detected: {', '.join(added)}")
            if removed:
                log(f"Removed plugins detected: {', '.join(removed)}")
            changed = True

        if old_marketplaces != current_marketplaces:
            added = current_marketplaces - old_marketplaces
            removed = old_marketplaces - current_marketplaces
            if added:
                log(f"New marketplaces detected: {', '.join(added)}")
            if removed:
                log(f"Removed marketplaces detected: {', '.join(removed)}")
            changed = True

        if not changed:
            log("Plugin list and marketplace list unchanged, no need to sync to Git")
        return changed
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

        log(f"✗ Failed to create snapshot: {result.stderr}")
        return False
    except Exception as e:
        log(f"✗ Error creating snapshot: {e}")
        return False


def sync_self_repo() -> bool:
    """同步 auto-manager 仓库自身（git pull），获取最新快照和配置

    在所有操作之前执行，确保使用最新的快照和配置文件。
    失败不影响后续流程。
    """
    try:
        log("Syncing auto-manager repo (git pull)...")
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SHORT,
            cwd=str(AUTO_MANAGER_DIR),
            check=False,
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            if "Already up to date" in output:
                log("✓ Auto-manager repo already up to date")
            else:
                first_line = output.split("\n")[0]
                log(f"✓ Auto-manager repo updated: {first_line}")
            return True

        log(f"✗ Failed to sync auto-manager repo: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        log("✗ Timeout syncing auto-manager repo")
        return False
    except Exception as e:
        log(f"✗ Error syncing auto-manager repo: {e}")
        return False


def ensure_self_registered() -> None:
    """确保 auto-manager 自身在 installed_plugins.json 中注册

    Claude Code 的插件操作可能会重建 installed_plugins.json，
    导致本地插件 auto-manager 的注册信息丢失，Hook 不再被触发。
    每次启动时检查并修复。
    """
    installed_file = CLAUDE_DIR / "plugins" / "installed_plugins.json"
    if not installed_file.exists():
        return

    try:
        data = json.loads(installed_file.read_text())
        plugins = data.get("plugins", {})

        if "auto-manager" in plugins:
            return

        log("auto-manager not found in installed_plugins.json, re-registering...")
        now = datetime.now(timezone.utc).isoformat()
        plugins["auto-manager"] = [
            {
                "scope": "user",
                "installPath": str(AUTO_MANAGER_DIR),
                "version": "1.0.0",
                "installedAt": now,
                "lastUpdated": now,
            }
        ]
        data["plugins"] = plugins

        temp_file = installed_file.with_suffix(".json.tmp")
        temp_file.write_text(json.dumps(data, indent=4) + "\n")
        temp_file.rename(installed_file)
        log("✓ auto-manager re-registered in installed_plugins.json")
    except Exception as e:
        log(f"Error ensuring self-registration: {e}")


def _build_hook_entry(command: str) -> Dict[str, Any]:
    """构建 SessionStart Hook 配置条目

    使用 matcher: "startup" 限制只在新会话启动时触发，
    避免在 resume/clear/compact 时重复运行。
    使用 async: true 让 Claude Code 负责后台化执行，
    不阻塞会话启动且避免 SIGHUP 导致子进程被杀死。
    """
    return {
        "matcher": "startup",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": HOOK_TIMEOUT,
                "async": True,
            }
        ]
    }


def ensure_global_hook() -> None:
    """确保 SessionStart Hook 在用户全局 settings.local.json 中注册

    将 Hook 从插件级别（hooks/hooks.json，依赖 installed_plugins.json）
    迁移到用户全局级别（~/.claude/settings.local.json），避免因
    installed_plugins.json 被重建导致 Hook 丢失的死循环问题。

    同时升级已有的旧配置（缺少 matcher 或 async 字段）为最新版本。
    """
    try:
        data = json.loads(GLOBAL_SETTINGS_LOCAL.read_text(encoding="utf-8")) if GLOBAL_SETTINGS_LOCAL.exists() else {}

        script_path = str(SESSION_START_SCRIPT)
        session_start_hooks = data.get("hooks", {}).get("SessionStart", [])

        # 查找已有的 Hook 条目
        existing_idx = None
        existing_hook_idx = None
        needs_upgrade = False
        for i, hook_group in enumerate(session_start_hooks):
            for j, hook in enumerate(hook_group.get("hooks", [])):
                if hook.get("command") == script_path:
                    existing_idx = i
                    existing_hook_idx = j
                    has_matcher = "matcher" in hook_group
                    has_async = hook.get("async") is True
                    has_correct_timeout = hook.get("timeout") == HOOK_TIMEOUT
                    needs_upgrade = not has_matcher or not has_async or not has_correct_timeout
                    break
            if existing_idx is not None:
                break

        if existing_idx is not None and not needs_upgrade:
            log("Global hook already configured in settings.local.json")
            return

        if needs_upgrade:
            hook_group = session_start_hooks[existing_idx]
            if "matcher" not in hook_group:
                hook_group["matcher"] = "startup"

            hook_entry = hook_group.get("hooks", [])[existing_hook_idx]
            if hook_entry.get("async") is not True:
                hook_entry["async"] = True
            if hook_entry.get("timeout") != HOOK_TIMEOUT:
                hook_entry["timeout"] = HOOK_TIMEOUT
            log("Upgrading global hook (adding matcher/async/timeout)")
        else:
            # 新增条目
            data.setdefault("hooks", {}).setdefault("SessionStart", []).append(
                _build_hook_entry(script_path)
            )

        # 原子写入
        GLOBAL_SETTINGS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        temp_file = GLOBAL_SETTINGS_LOCAL.with_suffix(".json.tmp")
        temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp_file.rename(GLOBAL_SETTINGS_LOCAL)
        log(f"✓ Global hook configured in {GLOBAL_SETTINGS_LOCAL}")
    except Exception as e:
        log(f"Error ensuring global hook: {e}")


def ensure_startup_service() -> None:
    """确保 OS 级启动服务（LaunchAgent/systemd/cron）已安装（自愈机制）

    只做轻量文件系统检查，不执行 launchctl/systemctl 命令。
    若服务缺失（如文件被误删），自动调用 startup-service.py 重新安装。
    异常不中断主流程。
    """
    try:
        if not STARTUP_SERVICE_SCRIPT.exists():
            log("startup-service.py not found, skipping OS service check")
            return

        spec = importlib.util.spec_from_file_location("startup_service", str(STARTUP_SERVICE_SCRIPT))
        startup_service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(startup_service)

        if startup_service.is_service_installed():
            log("OS startup service already installed")
            return

        log("OS startup service missing, reinstalling...")
        result = startup_service.install_service(AUTO_MANAGER_DIR)
        if result:
            log("✓ OS startup service reinstalled")
        else:
            log("✗ Failed to reinstall OS startup service")
    except Exception as e:
        log(f"Error ensuring OS startup service: {e}")


def sync_to_git(config: Dict[str, Any]) -> bool:
    """同步快照到 Git 仓库"""
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

        log(f"✗ Failed to sync to Git: {result.stderr}")
        return False
    except Exception as e:
        log(f"✗ Error syncing to Git: {e}")
        return False


def sync_marketplaces_from_snapshot() -> int:
    """将快照中缺失的 marketplace 同步到本地 known_marketplaces.json

    只添加缺失的 marketplace，不删除现有的。
    返回新添加的 marketplace 数量。
    """
    if not CURRENT_SNAPSHOT.exists():
        return 0

    try:
        snapshot = json.loads(CURRENT_SNAPSHOT.read_text())
        snapshot_marketplaces = snapshot.get("marketplaces", {})

        if not snapshot_marketplaces:
            return 0

        local_data: Dict[str, Any] = {}
        if KNOWN_MARKETPLACES_FILE.exists():
            local_data = json.loads(KNOWN_MARKETPLACES_FILE.read_text())

        missing = {
            name: info
            for name, info in snapshot_marketplaces.items()
            if name not in local_data
        }

        if not missing:
            log("All snapshot marketplaces are registered locally")
            return 0

        log(f"Found {len(missing)} new marketplace(s) from snapshot: {', '.join(missing.keys())}")

        for name, info in missing.items():
            # 重构 known_marketplaces.json 格式（source 字段为嵌套 dict）
            local_data[name] = {
                "source": {
                    "source": info.get("source", "github"),
                    "repo": info.get("repo", ""),
                },
                "autoUpdate": True,
            }
            log(f"Adding marketplace: {name} ({info.get('repo', 'unknown')})")

        # 原子写入
        KNOWN_MARKETPLACES_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = KNOWN_MARKETPLACES_FILE.with_suffix(".json.tmp")
        temp_file.write_text(json.dumps(local_data, indent=2) + "\n")
        temp_file.rename(KNOWN_MARKETPLACES_FILE)
        log(f"✓ Added {len(missing)} marketplace(s) to known_marketplaces.json")

        # 立即 fetch 新 marketplace 的插件列表（不在 Claude 会话中执行，避免嵌套错误）
        if not is_in_claude_session():
            for name in missing:
                _update_single_marketplace(name)
        else:
            log("Skipping marketplace fetch (running inside Claude session)")

        return len(missing)
    except Exception as e:
        log(f"Error syncing marketplaces from snapshot: {e}")
        return 0


def sync_global_rules(config: Dict[str, Any]) -> None:
    """将仓库中的全局规则同步到 ~/.claude/CLAUDE.md

    只在源文件存在且内容有变化时更新目标文件。
    """
    global_sync = config.get("global_sync", {})
    if not global_sync.get("enabled", False):
        log("Global rules sync is disabled in config")
        return

    if not GLOBAL_RULES_SOURCE.exists():
        log("Global rules source not found, skipping sync")
        return

    try:
        source_content = GLOBAL_RULES_SOURCE.read_text(encoding="utf-8")

        # 只在内容变化时更新
        if GLOBAL_RULES_TARGET.exists():
            target_content = GLOBAL_RULES_TARGET.read_text(encoding="utf-8")
            if source_content == target_content:
                log("Global rules unchanged, skipping sync")
                return

        # 确保目标目录存在
        GLOBAL_RULES_TARGET.parent.mkdir(parents=True, exist_ok=True)

        # 使用临时文件 + rename 实现原子写入
        temp_file = GLOBAL_RULES_TARGET.with_suffix(".md.tmp")
        temp_file.write_text(source_content, encoding="utf-8")
        temp_file.rename(GLOBAL_RULES_TARGET)
        log(f"✓ Global rules synced to {GLOBAL_RULES_TARGET}")
    except Exception as e:
        log(f"Error syncing global rules: {e}")


def sync_global_skills(config: Dict[str, Any]) -> None:
    """将仓库中的 global-skills/ 同步到 ~/.claude/skills/

    遍历 global-skills/ 下的每个子目录，将 SKILL.md 同步到对应的目标目录。
    只在源文件存在且内容有变化时更新。
    """
    global_skills_sync = config.get("global_skills_sync", {})
    if not global_skills_sync.get("enabled", False):
        log("Global skills sync is disabled in config")
        return

    if not GLOBAL_SKILLS_SOURCE_DIR.exists():
        log("Global skills source directory not found, skipping sync")
        return

    try:
        synced = 0
        for skill_dir in GLOBAL_SKILLS_SOURCE_DIR.iterdir():
            if not skill_dir.is_dir():
                continue

            source_file = skill_dir / "SKILL.md"
            if not source_file.exists():
                continue

            target_dir = GLOBAL_SKILLS_TARGET_DIR / skill_dir.name
            target_file = target_dir / "SKILL.md"

            try:
                source_content = source_file.read_text(encoding="utf-8")

                # 只在内容变化时更新
                if target_file.exists():
                    target_content = target_file.read_text(encoding="utf-8")
                    if source_content == target_content:
                        continue

                target_dir.mkdir(parents=True, exist_ok=True)

                temp_file = target_file.with_suffix(".md.tmp")
                temp_file.write_text(source_content, encoding="utf-8")
                temp_file.rename(target_file)
                log(f"✓ Synced skill: {skill_dir.name}")
                synced += 1
            except Exception as e:
                log(f"Error syncing skill {skill_dir.name}: {e}")

        if synced > 0:
            log(f"Synced {synced} skill(s) to {GLOBAL_SKILLS_TARGET_DIR}")
        else:
            log("All skills unchanged, skipping sync")
    except Exception as e:
        log(f"Error syncing global skills: {e}")


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


def escape_for_applescript(text: str) -> str:
    """转义 AppleScript 字符串中的特殊字符"""
    return text.replace('\\', '\\\\').replace('"', '\\"')


def escape_for_powershell(text: str) -> str:
    """转义 PowerShell 字符串中的特殊字符"""
    return text.replace('"', '`"').replace('$', '`$')


def send_notification(title: str, message: str) -> None:
    """发送系统通知（跨平台）"""
    import platform

    system = platform.system()

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

    # 确保自身在 installed_plugins.json 中注册（防止被插件更新操作覆盖）
    ensure_self_registered()

    # 确保全局 Hook 已配置（不依赖 installed_plugins.json）
    ensure_global_hook()

    # 确保 OS 级启动服务已安装（自愈：检测到缺失时重新安装）
    ensure_startup_service()

    # 双重运行防护：OS 服务和 Claude Code Hook 可能在同一次登录中都触发，
    # 若 5 分钟内已运行过则跳过（--force-update 参数可绕过此检查）
    if not args.force_update and LAST_UPDATE_FILE.exists():
        try:
            last_run = datetime.fromisoformat(LAST_UPDATE_FILE.read_text(encoding="utf-8").strip())
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_run).total_seconds()
            if elapsed < RECENT_RUN_THRESHOLD_SECONDS:
                log(f"Skipping: last run was {elapsed:.0f}s ago (< {RECENT_RUN_THRESHOLD_SECONDS}s cooldown)")
                log("========================================")
                log("Claude Plugin Auto-Manager Finished")
                log("========================================")
                return
        except Exception:
            pass  # 时间戳格式异常，继续正常执行

    # 0. 同步 auto-manager 仓库自身（拉取最新快照和配置）
    # 在 load_config() 之前执行，确保使用远程最新的配置和快照。
    # 不受 git_sync.enabled 控制，因为 git pull 是只读操作且配置尚未加载。
    sync_self_repo()

    # 加载配置（在 git pull 之后，确保使用最新配置）
    config = load_config()

    # 0.5. 将快照中的 marketplace 同步到本地（来自其他平台新增的 marketplace）
    sync_marketplaces_from_snapshot()

    # 检查安装前的插件列表变化
    plugins_changed = False

    # 1. 安装缺失的插件
    if config["auto_install"]["enabled"]:
        installed_count = install_missing_plugins()
        # claude plugin install 可能重建 installed_plugins.json，需要重新注册
        ensure_self_registered()
        if installed_count > 0:
            plugins_changed = True  # 安装了新插件，需要同步
            if config["auto_update"]["notify"]:
                send_notification(
                    "Auto-Install", f"Installed {installed_count} missing plugin(s)"
                )
    else:
        log("Auto-install is disabled in config")

    # 2. 同步全局规则到 ~/.claude/CLAUDE.md
    sync_global_rules(config)

    # 3. 同步全局 skills 到 ~/.claude/skills/
    sync_global_skills(config)

    # 4. 检查是否需要更新
    if args.force_update or should_update(config):
        # 先更新 marketplaces
        marketplace_updated = update_all_marketplaces()

        # 再更新插件
        update_count = update_all_plugins()
        # claude plugin update 可能重建 installed_plugins.json，需要重新注册
        ensure_self_registered()

        if update_count > 0:
            # 仅在有插件实际更新时才发送通知
            if config["auto_update"]["notify"]:
                msg = f"Updated marketplaces and {update_count} plugin(s)" if marketplace_updated > 0 else f"Updated {update_count} plugin(s)"
                send_notification("Auto-Update", msg)

        # 更新时间戳
        update_timestamp()

    # 5. 只在插件列表变化时才创建快照并同步到 Git
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
