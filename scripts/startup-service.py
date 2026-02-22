#!/usr/bin/env python3
"""
OS 级启动服务管理器

在用户登录时自动运行 auto-manager，替代依赖 Claude Code SessionStart Hook 的方式，
彻底绕开 Claude Code settings 浅合并导致的 Hook 遮蔽问题。

支持平台：
- macOS:          ~/Library/LaunchAgents/com.claude.auto-manager.plist
- Linux (systemd): ~/.config/systemd/user/claude-auto-manager.service
- Linux (cron):   @reboot crontab（systemd 不可用时的 fallback）
- DevContainer:   跳过（继续使用 Claude Code SessionStart Hook）
- Windows:        暂不支持，保持现有 Claude Code Hook 机制
"""
import importlib.util
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ============================================================
# 常量
# ============================================================

LAUNCHD_LABEL = "com.claude.auto-manager"
LAUNCHAGENT_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"

SERVICE_NAME = "claude-auto-manager"
SYSTEMD_SERVICE_PATH = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"

# 标记注释，用于识别 crontab 中的条目
CRON_MARKER = "# claude-auto-manager"

# 登录后延迟秒数，避免与系统资源争用
SERVICE_START_DELAY = 30

# 默认 auto-manager 部署路径
DEFAULT_PLUGIN_DIR = Path.home() / ".claude" / "plugins" / "auto-manager"


# ============================================================
# 平台检测
# ============================================================

def is_devcontainer() -> bool:
    """检测是否在 DevContainer / 容器环境中运行"""
    return (
        Path("/.dockerenv").exists()
        or bool(os.environ.get("REMOTE_CONTAINERS"))
        or bool(os.environ.get("CODESPACES"))
        or bool(os.environ.get("DEVCONTAINER"))
        or bool(os.environ.get("KUBERNETES_SERVICE_HOST"))
    )


def get_platform() -> str:
    """检测当前平台

    Returns:
        "macos" | "linux_systemd" | "linux_cron" | "devcontainer" | "windows" | "unknown"
    """
    # DevContainer 优先级最高
    if is_devcontainer():
        return "devcontainer"

    system = platform.system()

    if system == "Darwin":
        return "macos"

    if system == "Linux":
        # 检查 systemctl 是否可用（用户级 systemd）
        if shutil.which("systemctl"):
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "status"],
                    capture_output=True,
                    timeout=5,
                )
                # 返回码 0（active）或 3（inactive）都表示 systemd 可用
                if result.returncode in (0, 1, 3):
                    return "linux_systemd"
            except Exception:
                pass
        return "linux_cron"

    if system == "Windows":
        return "windows"

    return "unknown"


def get_python_path() -> str:
    """获取 Python 可执行文件的绝对路径

    launchd 和 systemd 的 PATH 极度受限，必须使用绝对路径。
    优先使用当前运行的 Python（最可靠），其次查找 python3。
    """
    # 当前运行的 Python（最可靠）
    if sys.executable and Path(sys.executable).exists():
        return sys.executable

    # 查找 python3
    python3 = shutil.which("python3")
    if python3:
        return python3

    # 最终 fallback
    return "python3"


# ============================================================
# 服务状态检测
# ============================================================

def is_service_installed() -> bool:
    """检测 OS 启动服务是否已安装（快速文件系统检查，不执行 OS 命令）

    Returns:
        True 表示服务已安装或当前平台无需 OS 服务（DevContainer）
    """
    plat = get_platform()

    if plat == "macos":
        return LAUNCHAGENT_PLIST_PATH.exists()

    if plat == "linux_systemd":
        return SYSTEMD_SERVICE_PATH.exists()

    if plat == "linux_cron":
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return CRON_MARKER in result.stdout
        except Exception:
            return False

    # DevContainer / Windows / unknown：视为"已安装"，跳过自愈
    return True


# ============================================================
# macOS LaunchAgent
# ============================================================

def install_launchagent(plugin_dir: Path, python_path: str) -> bool:
    """安装 macOS LaunchAgent

    Args:
        plugin_dir: auto-manager 部署根目录
        python_path: Python 可执行文件绝对路径

    Returns:
        True 表示安装成功（plist 文件已写入）
    """
    log_file = str(plugin_dir / "logs" / "auto-manager.log")
    auto_manager_script = str(plugin_dir / "scripts" / "auto-manager.py")

    plist_data = {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [
            "/bin/bash",
            "-c",
            f"sleep {SERVICE_START_DELAY} && unset CLAUDECODE CLAUDE_CODE_SESSION_ID && {python_path} {auto_manager_script}",
        ],
        "RunAtLoad": True,
        "StandardOutPath": log_file,
        "StandardErrorPath": log_file,
        # 补充 launchd 受限 PATH，确保能找到 git、claude 等命令
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(Path.home()),
        },
        # 避免异常退出后频繁重启
        "ThrottleInterval": 60,
    }

    try:
        LAUNCHAGENT_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 原子写入
        tmp_path = LAUNCHAGENT_PLIST_PATH.with_suffix(".plist.tmp")
        with open(tmp_path, "wb") as f:
            plistlib.dump(plist_data, f, fmt=plistlib.FMT_XML)
        tmp_path.rename(LAUNCHAGENT_PLIST_PATH)

        # 加载到 launchd（失败不影响返回值，文件已写入下次登录自动生效）
        subprocess.run(
            ["launchctl", "unload", str(LAUNCHAGENT_PLIST_PATH)],
            capture_output=True,
        )
        subprocess.run(
            ["launchctl", "load", str(LAUNCHAGENT_PLIST_PATH)],
            capture_output=True,
        )
        return True
    except Exception as e:
        print(f"LaunchAgent 安装失败: {e}", file=sys.stderr)
        return False


def uninstall_launchagent() -> bool:
    """卸载 macOS LaunchAgent"""
    try:
        if LAUNCHAGENT_PLIST_PATH.exists():
            subprocess.run(
                ["launchctl", "unload", str(LAUNCHAGENT_PLIST_PATH)],
                capture_output=True,
            )
            LAUNCHAGENT_PLIST_PATH.unlink()
        return True
    except Exception as e:
        print(f"LaunchAgent 卸载失败: {e}", file=sys.stderr)
        return False


# ============================================================
# Linux systemd 用户服务
# ============================================================

def install_systemd_service(plugin_dir: Path, python_path: str) -> bool:
    """安装 Linux systemd 用户服务

    Args:
        plugin_dir: auto-manager 部署根目录
        python_path: Python 可执行文件绝对路径

    Returns:
        True 表示安装成功
    """
    log_file = str(plugin_dir / "logs" / "auto-manager.log")
    auto_manager_script = str(plugin_dir / "scripts" / "auto-manager.py")

    service_content = f"""[Unit]
Description=Claude Plugin Auto-Manager
After=network.target

[Service]
Type=oneshot
ExecStartPre=/bin/sleep {SERVICE_START_DELAY}
ExecStart={python_path} {auto_manager_script}
Environment=HOME={Path.home()}
Environment=PATH=/usr/local/bin:/usr/bin:/bin
StandardOutput=append:{log_file}
StandardError=append:{log_file}
RemainAfterExit=no

[Install]
WantedBy=default.target
"""

    try:
        SYSTEMD_SERVICE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 原子写入
        tmp_path = SYSTEMD_SERVICE_PATH.with_suffix(".service.tmp")
        tmp_path.write_text(service_content, encoding="utf-8")
        tmp_path.rename(SYSTEMD_SERVICE_PATH)

        # 重载并启用服务
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=10)
        subprocess.run(
            ["systemctl", "--user", "enable", SERVICE_NAME],
            check=True,
            timeout=10,
        )
        # 首次立即运行一次
        subprocess.run(
            ["systemctl", "--user", "start", SERVICE_NAME],
            capture_output=True,
            timeout=10,
        )
        return True
    except Exception as e:
        print(f"systemd 服务安装失败: {e}", file=sys.stderr)
        return False


def uninstall_systemd_service() -> bool:
    """卸载 Linux systemd 用户服务"""
    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", SERVICE_NAME],
            capture_output=True,
            timeout=10,
        )
        if SYSTEMD_SERVICE_PATH.exists():
            SYSTEMD_SERVICE_PATH.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=10)
        return True
    except Exception as e:
        print(f"systemd 服务卸载失败: {e}", file=sys.stderr)
        return False


# ============================================================
# Linux cron fallback
# ============================================================

def install_cron_service(plugin_dir: Path, python_path: str) -> bool:
    """安装 Linux cron @reboot 条目

    Args:
        plugin_dir: auto-manager 部署根目录
        python_path: Python 可执行文件绝对路径

    Returns:
        True 表示安装成功
    """
    log_file = str(plugin_dir / "logs" / "auto-manager.log")
    auto_manager_script = str(plugin_dir / "scripts" / "auto-manager.py")

    cron_entry = (
        f"@reboot sleep {SERVICE_START_DELAY} && "
        f"unset CLAUDECODE CLAUDE_CODE_SESSION_ID && "
        f"{python_path} {auto_manager_script} >> {log_file} 2>&1 "
        f"{CRON_MARKER}"
    )

    try:
        # 读取现有 crontab
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        current = result.stdout if result.returncode == 0 else ""

        # 过滤掉旧条目
        lines = [line for line in current.splitlines() if CRON_MARKER not in line]
        lines.append(cron_entry)
        new_crontab = "\n".join(lines) + "\n"

        # 写回 crontab
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception as e:
        print(f"cron 配置失败: {e}", file=sys.stderr)
        return False


def uninstall_cron_service() -> bool:
    """卸载 cron @reboot 条目"""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return True  # crontab 为空，无需操作

        lines = [line for line in result.stdout.splitlines() if CRON_MARKER not in line]
        new_crontab = "\n".join(lines) + "\n" if lines else ""

        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception as e:
        print(f"cron 卸载失败: {e}", file=sys.stderr)
        return False


# ============================================================
# 统一入口
# ============================================================

def install_service(plugin_dir: Optional[Path] = None) -> bool:
    """安装 OS 级启动服务（根据平台自动选择）

    Args:
        plugin_dir: auto-manager 部署根目录，默认使用 ~/.claude/plugins/auto-manager

    Returns:
        True 表示安装成功或当前平台不需要安装
    """
    if plugin_dir is None:
        plugin_dir = DEFAULT_PLUGIN_DIR

    plat = get_platform()
    python_path = get_python_path()

    if plat == "devcontainer":
        print("DevContainer 环境，跳过 OS 服务安装（使用 Claude Code Hook）")
        return True

    if plat == "windows":
        print("Windows 暂不支持 OS 启动服务，保持现有 Claude Code Hook 机制")
        return True

    if plat == "macos":
        result = install_launchagent(plugin_dir, python_path)
        if result:
            print(f"✓ LaunchAgent 已安装: {LAUNCHAGENT_PLIST_PATH}")
        return result

    if plat == "linux_systemd":
        result = install_systemd_service(plugin_dir, python_path)
        if result:
            print(f"✓ systemd 用户服务已配置: {SERVICE_NAME}")
        return result

    if plat == "linux_cron":
        result = install_cron_service(plugin_dir, python_path)
        if result:
            print(f"✓ crontab @reboot 已配置 ({CRON_MARKER})")
        return result

    print(f"未知平台 ({plat})，跳过 OS 服务安装")
    return True


def uninstall_service() -> bool:
    """卸载 OS 级启动服务（根据平台自动选择）

    Returns:
        True 表示卸载成功或当前平台无服务可卸载
    """
    plat = get_platform()

    if plat == "macos":
        result = uninstall_launchagent()
        if result:
            print(f"✓ LaunchAgent 已卸载: {LAUNCHAGENT_PLIST_PATH}")
        return result

    if plat == "linux_systemd":
        result = uninstall_systemd_service()
        if result:
            print(f"✓ systemd 用户服务已卸载: {SERVICE_NAME}")
        return result

    if plat == "linux_cron":
        result = uninstall_cron_service()
        if result:
            print("✓ crontab @reboot 已移除")
        return result

    return True


def check_service_status() -> None:
    """打印当前 OS 服务安装状态"""
    plat = get_platform()
    installed = is_service_installed()

    print(f"平台:     {plat}")
    print(f"Python:   {get_python_path()}")
    print(f"已安装:   {'是' if installed else '否'}")

    if plat == "macos":
        print(f"服务文件: {LAUNCHAGENT_PLIST_PATH}")
    elif plat == "linux_systemd":
        print(f"服务文件: {SYSTEMD_SERVICE_PATH}")
    elif plat == "linux_cron":
        print(f"标记:     {CRON_MARKER}")


# ============================================================
# 命令行入口
# ============================================================

def main() -> None:
    """命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Claude Auto-Manager OS 启动服务管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 startup-service.py --install              安装 OS 启动服务
  python3 startup-service.py --uninstall            卸载 OS 启动服务
  python3 startup-service.py --check                查看当前状态
  python3 startup-service.py --check-and-install    检查并在缺失时安装
""",
    )
    parser.add_argument("--install", action="store_true", help="安装 OS 启动服务")
    parser.add_argument("--uninstall", action="store_true", help="卸载 OS 启动服务")
    parser.add_argument("--check", action="store_true", help="查看当前状态")
    parser.add_argument("--check-and-install", action="store_true", help="检查并在缺失时安装")
    parser.add_argument(
        "--plugin-dir",
        type=Path,
        default=DEFAULT_PLUGIN_DIR,
        help=f"auto-manager 部署目录（默认: {DEFAULT_PLUGIN_DIR}）",
    )

    args = parser.parse_args()

    if args.check:
        check_service_status()
    elif args.install:
        sys.exit(0 if install_service(args.plugin_dir) else 1)
    elif args.uninstall:
        sys.exit(0 if uninstall_service() else 1)
    elif args.check_and_install:
        if not is_service_installed():
            print("OS 启动服务未安装，正在安装...")
            sys.exit(0 if install_service(args.plugin_dir) else 1)
        else:
            print("OS 启动服务已安装，无需操作")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
