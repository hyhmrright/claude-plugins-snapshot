#!/usr/bin/env python3
"""
Claude Code 插件自动管理器 - 跨平台安装脚本
支持 macOS、Linux、Windows、DevContainer
"""
import importlib.util
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def log_info(message: str) -> None:
    """输出信息"""
    print(f"✓ {message}")


def log_warn(message: str) -> None:
    """输出警告"""
    print(f"⚠ {message}")


def log_error(message: str) -> None:
    """输出错误"""
    print(f"✗ {message}", file=sys.stderr)


def get_claude_dir() -> Path:
    """获取 Claude 配置目录（跨平台）"""
    system = platform.system()

    if system == "Windows":
        # Windows: %APPDATA%\Claude
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "Claude"
        # 备选：用户目录下的 .claude
        return Path.home() / ".claude"
    else:
        # macOS/Linux/DevContainer: ~/.claude
        return Path.home() / ".claude"


def check_dependencies() -> bool:
    """检查依赖"""
    log_info("检查依赖...")

    # 检查 Python 版本
    if sys.version_info < (3, 8):
        log_error("需要 Python 3.8 或更高版本")
        return False

    # 检查 Git
    if not shutil.which("git"):
        log_error("Git 未安装，请先安装 Git")
        return False

    # 检查 Claude 配置目录
    claude_dir = get_claude_dir()
    if not claude_dir.exists():
        log_error(f"Claude Code 配置目录不存在: {claude_dir}")
        log_error("请先安装并运行 Claude Code")
        return False

    log_info(f"Claude 配置目录: {claude_dir}")
    return True


def backup_config(file_path: Path) -> None:
    """备份配置文件"""
    if file_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_path = file_path.with_suffix(f".backup.{timestamp}")
        shutil.copy2(file_path, backup_path)
        log_info(f"已备份: {backup_path.name}")


def update_settings_json(plugin_dir: Path) -> bool:
    """更新 settings.json"""
    claude_dir = get_claude_dir()
    settings_file = claude_dir / "settings.json"

    if not settings_file.exists():
        log_error("settings.json 不存在")
        return False

    try:
        # 备份
        backup_config(settings_file)

        # 读取
        settings = json.loads(settings_file.read_text(encoding="utf-8"))

        # 确保 enabledPlugins 存在
        if "enabledPlugins" not in settings:
            settings["enabledPlugins"] = {}

        # 检查是否已安装
        if "auto-manager" in settings["enabledPlugins"]:
            log_warn("插件已在 settings.json 中")
            response = input("是否重新安装？(y/N) ")
            if response.lower() != "y":
                return True

        # 添加插件
        settings["enabledPlugins"]["auto-manager"] = True

        # 保存
        settings_file.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        log_info("已更新 settings.json")
        return True
    except Exception as e:
        log_error(f"更新 settings.json 失败: {e}")
        return False


def update_installed_plugins(plugin_dir: Path) -> bool:
    """更新 installed_plugins.json"""
    claude_dir = get_claude_dir()
    installed_file = claude_dir / "plugins" / "installed_plugins.json"

    if not installed_file.exists():
        log_error("installed_plugins.json 不存在")
        return False

    try:
        # 备份
        backup_config(installed_file)

        # 读取
        installed = json.loads(installed_file.read_text(encoding="utf-8"))

        # 确保 plugins 存在
        if "plugins" not in installed:
            installed["plugins"] = {}

        # 添加插件记录
        installed["plugins"]["auto-manager"] = [
            {
                "scope": "user",
                "installPath": str(plugin_dir),
                "version": "1.0.0",
                "installedAt": datetime.now(timezone.utc).isoformat(),
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
            }
        ]

        # 保存
        installed_file.write_text(
            json.dumps(installed, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        log_info("已更新 installed_plugins.json")
        return True
    except Exception as e:
        log_error(f"更新 installed_plugins.json 失败: {e}")
        return False


def set_permissions(plugin_dir: Path) -> None:
    """设置脚本执行权限（Unix 系统）"""
    if platform.system() != "Windows":
        log_info("设置脚本执行权限...")
        scripts_dir = plugin_dir / "scripts"
        # 0o744：所有者可读写执行，组和其他用户只读
        for pattern in ("*.sh", "*.py"):
            for script in scripts_dir.glob(pattern):
                script.chmod(0o744)


def _build_hook_entry(command: str) -> dict:
    """构建 SessionStart Hook 配置条目"""
    return {
        "matcher": "startup",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": 120,
                "async": True,
            }
        ]
    }


def setup_global_hook(plugin_dir: Path) -> bool:
    """在 ~/.claude/settings.local.json 中设置全局 SessionStart Hook"""
    claude_dir = get_claude_dir()
    settings_local = claude_dir / "settings.local.json"
    script_path = str(plugin_dir / "scripts" / "session-start.sh")

    try:
        data = json.loads(settings_local.read_text(encoding="utf-8")) if settings_local.exists() else {}

        session_start_hooks = data.get("hooks", {}).get("SessionStart", [])
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
                    needs_upgrade = not has_matcher or not has_async
                    break
            if existing_idx is not None:
                break

        if existing_idx is not None and not needs_upgrade:
            log_info("全局 Hook 已配置")
            return True

        if existing_idx is not None:
            hook_group = session_start_hooks[existing_idx]
            if "matcher" not in hook_group:
                hook_group["matcher"] = "startup"

            hook_entry = hook_group.get("hooks", [])[existing_hook_idx]
            if hook_entry.get("async") is not True:
                hook_entry["async"] = True
            log_info("升级全局 Hook 配置（添加 matcher/async）")
        else:
            data.setdefault("hooks", {}).setdefault("SessionStart", []).append(
                _build_hook_entry(script_path)
            )

        # 原子写入
        settings_local.parent.mkdir(parents=True, exist_ok=True)
        temp_file = settings_local.with_suffix(".json.tmp")
        temp_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temp_file.rename(settings_local)
        log_info(f"已配置全局 Hook: {settings_local}")
        return True
    except Exception as e:
        log_error(f"配置全局 Hook 失败: {e}")
        return False


def install_startup_service(plugin_dir: Path) -> None:
    """安装 OS 级启动服务（macOS LaunchAgent / Linux systemd / cron）

    Args:
        plugin_dir: auto-manager 部署根目录
    """
    startup_script = plugin_dir / "scripts" / "startup-service.py"
    if not startup_script.exists():
        log_warn("startup-service.py 未找到，跳过 OS 服务安装")
        return

    try:
        spec = importlib.util.spec_from_file_location("startup_service", str(startup_script))
        startup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(startup_module)

        plat = startup_module.get_platform()
        if plat == "devcontainer":
            log_warn("DevContainer 环境，跳过 OS 服务安装（使用 Claude Code Hook）")
            return
        if plat == "windows":
            log_warn("Windows 暂不支持 OS 启动服务，保持现有 Claude Code Hook 机制")
            return

        result = startup_module.install_service(plugin_dir)
        if result:
            log_info("OS 启动服务已配置（登录时自动运行）")
        else:
            log_warn("OS 启动服务配置失败（Claude Code Hook 将作为备用）")
    except Exception as e:
        log_warn(f"OS 启动服务配置跳过: {e}")


def check_snapshot(plugin_dir: Path) -> None:
    """检查快照文件"""
    snapshot_file = plugin_dir / "snapshots" / "current.json"

    if snapshot_file.exists():
        try:
            snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
            plugin_count = len(snapshot.get("plugins", {}))
            log_info(f"发现快照文件，包含 {plugin_count} 个插件")
            log_warn("下次启动 Claude Code 时，将自动安装快照中的插件")
        except Exception as e:
            log_warn(f"无法读取快照文件: {e}")
    else:
        log_warn("未找到快照文件，将在首次运行时生成")


def main() -> int:
    """主函数"""
    print("=" * 50)
    print("Claude Plugin Auto-Manager 安装脚本")
    print(f"平台: {platform.system()} {platform.release()}")
    print("=" * 50)
    print()

    # 获取插件目录（脚本所在目录）
    plugin_dir = Path(__file__).parent.resolve()
    log_info(f"插件目录: {plugin_dir}")

    # 1. 检查依赖
    if not check_dependencies():
        return 1

    # 2. 设置脚本权限
    set_permissions(plugin_dir)

    # 3. 更新 settings.json
    if not update_settings_json(plugin_dir):
        return 1

    # 4. 更新 installed_plugins.json
    if not update_installed_plugins(plugin_dir):
        return 1

    # 5. 设置全局 Hook（不依赖 installed_plugins.json，作为 DevContainer 和 fallback）
    setup_global_hook(plugin_dir)

    # 5.5. 安装 OS 级启动服务（主要机制，不依赖 Claude Code Hook）
    install_startup_service(plugin_dir)

    # 6. 检查快照
    check_snapshot(plugin_dir)

    # 7. 创建日志目录
    logs_dir = plugin_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    print()
    print("=" * 50)
    log_info("安装完成！")
    print("=" * 50)
    print()
    print("下一步：")
    print("  1. 重启 Claude Code")
    print("  2. 插件将自动运行，检查并安装缺失的插件")
    print(f"  3. 查看日志: {logs_dir / 'auto-manager.log'}")
    print()
    print(f"配置文件: {plugin_dir / 'config.json'}")
    print(f"快照文件: {plugin_dir / 'snapshots' / 'current.json'}")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n已取消安装")
        sys.exit(1)
    except Exception as e:
        log_error(f"安装失败: {e}")
        sys.exit(1)
