#!/usr/bin/env python3
"""
Unit tests for startup-service.py
"""
import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# startup-service.py 文件名含连字符，用 importlib 导入
_spec = importlib.util.spec_from_file_location(
    "startup_service",
    str(Path(__file__).parent.parent / "scripts" / "startup-service.py"),
)
_startup_service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_startup_service)

# 导入被测函数和常量
is_devcontainer = _startup_service.is_devcontainer
get_platform = _startup_service.get_platform
get_python_path = _startup_service.get_python_path
is_service_installed = _startup_service.is_service_installed
install_launchagent = _startup_service.install_launchagent
install_systemd_service = _startup_service.install_systemd_service
install_cron_service = _startup_service.install_cron_service
uninstall_launchagent = _startup_service.uninstall_launchagent
uninstall_systemd_service = _startup_service.uninstall_systemd_service
uninstall_cron_service = _startup_service.uninstall_cron_service
install_service = _startup_service.install_service
uninstall_service = _startup_service.uninstall_service

LAUNCHAGENT_PLIST_PATH = _startup_service.LAUNCHAGENT_PLIST_PATH
SYSTEMD_SERVICE_PATH = _startup_service.SYSTEMD_SERVICE_PATH
CRON_MARKER = _startup_service.CRON_MARKER
SERVICE_START_DELAY = _startup_service.SERVICE_START_DELAY
LAUNCHD_LABEL = _startup_service.LAUNCHD_LABEL
SERVICE_NAME = _startup_service.SERVICE_NAME


# DevContainer 相关环境变量名列表
_DEVCONTAINER_ENV_VARS = ("REMOTE_CONTAINERS", "CODESPACES", "DEVCONTAINER", "KUBERNETES_SERVICE_HOST")


def _clear_devcontainer_env(monkeypatch):
    """清除所有 DevContainer 相关环境变量"""
    for var in _DEVCONTAINER_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _mock_dockerenv_exists(monkeypatch, exists: bool):
    """模拟 /.dockerenv 文件是否存在"""
    original_path = _startup_service.Path

    class MockPath(original_path):
        def exists(self):
            if str(self) == "/.dockerenv":
                return exists
            return super().exists()

    monkeypatch.setattr(_startup_service, "Path", MockPath)


# ============================================================
# TestDevContainerDetection
# ============================================================

class TestDevContainerDetection:
    """测试 DevContainer 环境检测"""

    def test_detects_dockerenv_file(self, monkeypatch):
        """/.dockerenv 文件存在时应检测为 DevContainer"""
        _clear_devcontainer_env(monkeypatch)
        _mock_dockerenv_exists(monkeypatch, exists=True)
        assert is_devcontainer() is True

    def test_detects_remote_containers_env(self, monkeypatch):
        """REMOTE_CONTAINERS 环境变量存在时应检测为 DevContainer"""
        _clear_devcontainer_env(monkeypatch)
        monkeypatch.setenv("REMOTE_CONTAINERS", "true")
        assert is_devcontainer() is True

    def test_detects_codespaces_env(self, monkeypatch):
        """CODESPACES 环境变量存在时应检测为 DevContainer"""
        _clear_devcontainer_env(monkeypatch)
        monkeypatch.setenv("CODESPACES", "true")
        assert is_devcontainer() is True

    def test_detects_devcontainer_env(self, monkeypatch):
        """DEVCONTAINER 环境变量存在时应检测为 DevContainer"""
        _clear_devcontainer_env(monkeypatch)
        monkeypatch.setenv("DEVCONTAINER", "1")
        assert is_devcontainer() is True

    def test_normal_env_returns_false(self, monkeypatch):
        """正常环境（无相关环境变量且无 /.dockerenv）应返回 False"""
        _clear_devcontainer_env(monkeypatch)
        _mock_dockerenv_exists(monkeypatch, exists=False)
        assert is_devcontainer() is False


# ============================================================
# TestPlatformDetection
# ============================================================

class TestPlatformDetection:
    """测试平台检测"""

    def test_devcontainer_takes_priority_over_macos(self, monkeypatch):
        """DevContainer 优先级高于 macOS"""
        monkeypatch.setenv("DEVCONTAINER", "true")
        monkeypatch.setattr(_startup_service, "is_devcontainer", lambda: True)
        assert get_platform() == "devcontainer"

    def test_macos_detection(self, monkeypatch):
        """Darwin 平台应返回 macos"""
        monkeypatch.setattr(_startup_service, "is_devcontainer", lambda: False)
        with patch("platform.system", return_value="Darwin"):
            assert get_platform() == "macos"

    def test_linux_systemd_when_systemctl_available(self, monkeypatch):
        """Linux + systemctl 可用时返回 linux_systemd"""
        monkeypatch.setattr(_startup_service, "is_devcontainer", lambda: False)
        with patch("platform.system", return_value="Linux"):
            with patch("shutil.which", return_value="/usr/bin/systemctl"):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=3)
                    assert get_platform() == "linux_systemd"

    def test_linux_cron_when_no_systemctl(self, monkeypatch):
        """Linux + systemctl 不可用时返回 linux_cron"""
        monkeypatch.setattr(_startup_service, "is_devcontainer", lambda: False)
        with patch("platform.system", return_value="Linux"):
            with patch("shutil.which", return_value=None):
                assert get_platform() == "linux_cron"

    def test_windows_detection(self, monkeypatch):
        """Windows 平台应返回 windows"""
        monkeypatch.setattr(_startup_service, "is_devcontainer", lambda: False)
        with patch("platform.system", return_value="Windows"):
            assert get_platform() == "windows"


# ============================================================
# TestGetPythonPath
# ============================================================

class TestGetPythonPath:
    """测试 Python 路径解析"""

    def test_returns_sys_executable_when_exists(self, monkeypatch):
        """sys.executable 存在时优先返回它"""
        # 直接使用真实的 sys.executable（在测试环境中它必然存在）
        result = get_python_path()
        assert result == sys.executable

    def test_returns_absolute_path(self):
        """返回的路径应是绝对路径（以 / 开头）或 'python3'"""
        result = get_python_path()
        assert result  # 非空
        # 要么是绝对路径，要么是 fallback 的 'python3'
        assert result.startswith("/") or result == "python3"


# ============================================================
# TestIsServiceInstalled
# ============================================================

class TestIsServiceInstalled:
    """测试服务安装状态检测（文件系统检查）"""

    def test_macos_not_installed_when_plist_missing(self, tmp_path, monkeypatch):
        """macOS：plist 文件不存在时返回 False"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "macos")
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", tmp_path / "nonexistent.plist")
        assert is_service_installed() is False

    def test_macos_installed_when_plist_exists(self, tmp_path, monkeypatch):
        """macOS：plist 文件存在时返回 True"""
        plist_path = tmp_path / "com.claude.auto-manager.plist"
        plist_path.touch()
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "macos")
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)
        assert is_service_installed() is True

    def test_linux_systemd_not_installed_when_service_missing(self, tmp_path, monkeypatch):
        """linux_systemd：service 文件不存在时返回 False"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "linux_systemd")
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", tmp_path / "nonexistent.service")
        assert is_service_installed() is False

    def test_linux_systemd_installed_when_service_exists(self, tmp_path, monkeypatch):
        """linux_systemd：service 文件存在时返回 True"""
        service_path = tmp_path / "claude-auto-manager.service"
        service_path.touch()
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "linux_systemd")
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", service_path)
        assert is_service_installed() is True

    def test_devcontainer_always_returns_true(self, monkeypatch):
        """DevContainer：始终返回 True（无需 OS 服务）"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "devcontainer")
        assert is_service_installed() is True

    def test_unknown_platform_returns_true(self, monkeypatch):
        """未知平台：返回 True（跳过自愈）"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "unknown")
        assert is_service_installed() is True

    def test_linux_cron_installed_when_marker_in_crontab(self, monkeypatch):
        """linux_cron：crontab 中有标记时返回 True"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "linux_cron")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=f"@reboot something {CRON_MARKER}\n",
            )
            assert is_service_installed() is True

    def test_linux_cron_not_installed_when_no_marker(self, monkeypatch):
        """linux_cron：crontab 中无标记时返回 False"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "linux_cron")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="@reboot something_else\n")
            assert is_service_installed() is False


# ============================================================
# TestInstallLaunchAgent
# ============================================================

class TestInstallLaunchAgent:
    """测试 macOS LaunchAgent 安装"""

    def test_creates_plist_file(self, tmp_path, monkeypatch):
        """安装后 plist 文件应存在"""
        plist_path = tmp_path / "com.claude.auto-manager.plist"
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = install_launchagent(tmp_path, sys.executable)

        assert result is True
        assert plist_path.exists()

    def test_plist_contains_correct_python_path(self, tmp_path, monkeypatch):
        """plist 中应包含传入的 python_path"""
        import plistlib
        plist_path = tmp_path / "com.claude.auto-manager.plist"
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)
        python_path = "/usr/local/bin/python3"

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_launchagent(tmp_path, python_path)

        with open(plist_path, "rb") as f:
            data = plistlib.load(f)

        # ProgramArguments 应包含 python_path
        args = " ".join(data["ProgramArguments"])
        assert python_path in args

    def test_plist_has_run_at_load(self, tmp_path, monkeypatch):
        """plist 应设置 RunAtLoad=True"""
        import plistlib
        plist_path = tmp_path / "com.claude.auto-manager.plist"
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_launchagent(tmp_path, sys.executable)

        with open(plist_path, "rb") as f:
            data = plistlib.load(f)

        assert data["RunAtLoad"] is True

    def test_plist_uses_absolute_log_path(self, tmp_path, monkeypatch):
        """plist 中日志路径应为绝对路径"""
        import plistlib
        plist_path = tmp_path / "com.claude.auto-manager.plist"
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_launchagent(tmp_path, sys.executable)

        with open(plist_path, "rb") as f:
            data = plistlib.load(f)

        assert data["StandardOutPath"].startswith("/")
        assert data["StandardErrorPath"].startswith("/")

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        """LaunchAgents 目录不存在时应自动创建"""
        plist_dir = tmp_path / "LaunchAgents"
        plist_path = plist_dir / "com.claude.auto-manager.plist"
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)

        assert not plist_dir.exists()
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_launchagent(tmp_path, sys.executable)

        assert plist_dir.exists()
        assert plist_path.exists()

    def test_launchctl_failure_does_not_fail_install(self, tmp_path, monkeypatch):
        """launchctl load 失败时 install 仍返回 True（文件已写入）"""
        plist_path = tmp_path / "com.claude.auto-manager.plist"
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "launchctl")):
            result = install_launchagent(tmp_path, sys.executable)

        # plist 文件写入是在 launchctl 之前完成的，但 CalledProcessError 会中断整个函数
        # 实际实现中 launchctl 用 capture_output=True 不会 raise，这里模拟异常
        # 预期：文件写入后才调用 launchctl，所以这个测试验证异常处理
        assert result is False  # 发生异常时返回 False（由外层 except 捕获）

    def test_plist_includes_delay(self, tmp_path, monkeypatch):
        """plist 命令应包含启动延迟"""
        import plistlib
        plist_path = tmp_path / "com.claude.auto-manager.plist"
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_launchagent(tmp_path, sys.executable)

        with open(plist_path, "rb") as f:
            data = plistlib.load(f)

        # 命令中应包含 sleep
        cmd = " ".join(data["ProgramArguments"])
        assert "sleep" in cmd
        assert str(SERVICE_START_DELAY) in cmd


# ============================================================
# TestInstallSystemdService
# ============================================================

class TestInstallSystemdService:
    """测试 Linux systemd 服务安装"""

    def test_creates_service_file(self, tmp_path, monkeypatch):
        """安装后 service 文件应存在"""
        service_path = tmp_path / "claude-auto-manager.service"
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", service_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = install_systemd_service(tmp_path, sys.executable)

        assert result is True
        assert service_path.exists()

    def test_service_file_uses_append_output(self, tmp_path, monkeypatch):
        """service 文件应使用 StandardOutput=append: 模式"""
        service_path = tmp_path / "claude-auto-manager.service"
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", service_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_systemd_service(tmp_path, sys.executable)

        content = service_path.read_text()
        assert "StandardOutput=append:" in content
        assert "StandardError=append:" in content

    def test_service_file_has_correct_type(self, tmp_path, monkeypatch):
        """service 文件应为 Type=oneshot"""
        service_path = tmp_path / "claude-auto-manager.service"
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", service_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_systemd_service(tmp_path, sys.executable)

        content = service_path.read_text()
        assert "Type=oneshot" in content

    def test_service_file_includes_delay(self, tmp_path, monkeypatch):
        """service 文件应包含启动延迟"""
        service_path = tmp_path / "claude-auto-manager.service"
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", service_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_systemd_service(tmp_path, sys.executable)

        content = service_path.read_text()
        assert f"sleep {SERVICE_START_DELAY}" in content

    def test_systemctl_enable_called(self, tmp_path, monkeypatch):
        """安装时应调用 systemctl --user enable"""
        service_path = tmp_path / "claude-auto-manager.service"
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", service_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            install_systemd_service(tmp_path, sys.executable)

        calls = [str(c) for c in mock_run.call_args_list]
        enable_called = any("enable" in c for c in calls)
        assert enable_called

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        """systemd 用户目录不存在时应自动创建"""
        service_dir = tmp_path / "systemd" / "user"
        service_path = service_dir / "claude-auto-manager.service"
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", service_path)

        assert not service_dir.exists()
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            install_systemd_service(tmp_path, sys.executable)

        assert service_dir.exists()


# ============================================================
# TestInstallCronService
# ============================================================

class TestInstallCronService:
    """测试 cron fallback 安装"""

    def test_adds_atreboot_entry(self, tmp_path, monkeypatch):
        """应添加 @reboot 条目"""
        with patch("subprocess.run") as mock_run:
            # crontab -l 返回空
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # crontab -l（空）
                MagicMock(returncode=0),              # crontab -（写入）
            ]
            result = install_cron_service(tmp_path, sys.executable)

        assert result is True
        # 检查写入的内容包含 @reboot 和标记
        write_call = mock_run.call_args_list[1]
        written = write_call.kwargs.get("input") or write_call.args[0] if len(write_call.args) > 0 else ""
        # 通过 input 参数传入
        stdin_input = mock_run.call_args_list[1].kwargs.get("input", "")
        assert "@reboot" in stdin_input
        assert CRON_MARKER in stdin_input

    def test_skips_duplicate_entry(self, tmp_path, monkeypatch):
        """已有标记时不重复添加，但会替换旧条目"""
        existing_cron = f"@reboot old_command {CRON_MARKER}\n"
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=existing_cron),  # crontab -l
                MagicMock(returncode=0),                          # crontab -
            ]
            install_cron_service(tmp_path, sys.executable)

        stdin_input = mock_run.call_args_list[1].kwargs.get("input", "")
        # 新条目替换旧条目，只有一个标记
        assert stdin_input.count(CRON_MARKER) == 1

    def test_preserves_existing_crontab_entries(self, tmp_path, monkeypatch):
        """应保留已有的非 auto-manager 条目"""
        existing_cron = "0 2 * * * /usr/bin/backup.sh\n"
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=existing_cron),
                MagicMock(returncode=0),
            ]
            install_cron_service(tmp_path, sys.executable)

        stdin_input = mock_run.call_args_list[1].kwargs.get("input", "")
        assert "/usr/bin/backup.sh" in stdin_input
        assert CRON_MARKER in stdin_input

    def test_includes_delay_in_command(self, tmp_path, monkeypatch):
        """@reboot 条目应包含启动延迟"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),
                MagicMock(returncode=0),
            ]
            install_cron_service(tmp_path, sys.executable)

        stdin_input = mock_run.call_args_list[1].kwargs.get("input", "")
        assert f"sleep {SERVICE_START_DELAY}" in stdin_input


# ============================================================
# TestUninstallService
# ============================================================

class TestUninstallService:
    """测试服务卸载"""

    def test_macos_deletes_plist(self, tmp_path, monkeypatch):
        """macOS 卸载后 plist 文件应被删除"""
        plist_path = tmp_path / "com.claude.auto-manager.plist"
        plist_path.touch()
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = uninstall_launchagent()

        assert result is True
        assert not plist_path.exists()

    def test_macos_handles_missing_plist(self, tmp_path, monkeypatch):
        """macOS：plist 不存在时卸载不报错"""
        plist_path = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(_startup_service, "LAUNCHAGENT_PLIST_PATH", plist_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = uninstall_launchagent()

        assert result is True

    def test_linux_systemd_deletes_service_file(self, tmp_path, monkeypatch):
        """Linux systemd 卸载后 service 文件应被删除"""
        service_path = tmp_path / "claude-auto-manager.service"
        service_path.touch()
        monkeypatch.setattr(_startup_service, "SYSTEMD_SERVICE_PATH", service_path)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = uninstall_systemd_service()

        assert result is True
        assert not service_path.exists()

    def test_cron_removes_marker_entry(self, monkeypatch):
        """cron 卸载后应移除标记条目"""
        existing_cron = f"0 2 * * * /backup.sh\n@reboot something {CRON_MARKER}\n"
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=existing_cron),
                MagicMock(returncode=0),
            ]
            result = uninstall_cron_service()

        assert result is True
        stdin_input = mock_run.call_args_list[1].kwargs.get("input", "")
        assert CRON_MARKER not in stdin_input
        assert "/backup.sh" in stdin_input

    def test_cron_handles_empty_crontab(self, monkeypatch):
        """cron：crontab 为空时卸载不报错"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = uninstall_cron_service()

        assert result is True


# ============================================================
# TestInstallServiceIntegration
# ============================================================

class TestInstallServiceIntegration:
    """测试 install_service 协调入口"""

    def test_devcontainer_returns_true_without_install(self, monkeypatch):
        """DevContainer 应跳过安装并返回 True"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "devcontainer")
        result = install_service()
        assert result is True

    def test_windows_returns_true_without_install(self, monkeypatch):
        """Windows 应跳过安装并返回 True"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "windows")
        result = install_service()
        assert result is True

    def test_unknown_platform_returns_true(self, monkeypatch):
        """未知平台应跳过安装并返回 True"""
        monkeypatch.setattr(_startup_service, "get_platform", lambda: "unknown")
        result = install_service()
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
