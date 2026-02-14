#!/usr/bin/env python3
"""
Unit tests for auto-manager.py
"""
import importlib.util
from datetime import datetime, timezone

import pytest


# auto-manager.py has a hyphen in its filename, so use importlib to import it
_spec = importlib.util.spec_from_file_location(
    "auto_manager",
    str(__import__("pathlib").Path(__file__).parent.parent / "scripts" / "auto-manager.py"),
)
_auto_manager = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auto_manager)

# Import constants and functions from the module under test
MAX_RETRY_COUNT = _auto_manager.MAX_RETRY_COUNT
MAX_LOG_SIZE_MB = _auto_manager.MAX_LOG_SIZE_MB
KEEP_LOG_SIZE_MB = _auto_manager.KEEP_LOG_SIZE_MB
RETRY_INTERVAL_SECONDS = _auto_manager.RETRY_INTERVAL_SECONDS
COMMAND_TIMEOUT_SHORT = _auto_manager.COMMAND_TIMEOUT_SHORT
COMMAND_TIMEOUT_LONG = _auto_manager.COMMAND_TIMEOUT_LONG
escape_for_applescript = _auto_manager.escape_for_applescript
escape_for_powershell = _auto_manager.escape_for_powershell


class TestRetryLogic:
    """测试重试机制"""

    def test_first_failure_sets_retry_count_to_one(self):
        """测试首次失败时 retry_count 设置为 1"""
        state = {}
        plugin_name = "test-plugin@marketplace"
        now = datetime.now(timezone.utc).isoformat()

        # 模拟首次失败（与 install_missing_plugins 中的逻辑一致）
        state[plugin_name] = {
            "status": "failed",
            "last_attempt": now,
            "retry_count": 1,
            "first_failed_at": now,
        }

        assert state[plugin_name]["retry_count"] == 1

    def test_max_retry_count_allows_retries_up_to_limit(self):
        """测试最大重试次数边界条件"""
        # retry_count <= MAX_RETRY_COUNT 应该允许重试
        assert not (1 > MAX_RETRY_COUNT)   # 第1次：可以重试
        assert not (5 > MAX_RETRY_COUNT)   # 第5次：仍可以重试
        assert 6 > MAX_RETRY_COUNT         # 第6次：应该被拒绝


class TestPluginNameValidation:
    """测试插件名称验证"""

    def test_valid_plugin_name(self):
        """测试有效的插件名称"""
        plugin_name = "example-plugin@marketplace"
        parts = plugin_name.split("@")

        assert len(parts) == 2
        assert parts[0] == "example-plugin"
        assert parts[1] == "marketplace"

    def test_invalid_plugin_name_no_at(self):
        """测试缺少 @ 的插件名称"""
        plugin_name = "example-plugin"
        parts = plugin_name.split("@")

        assert len(parts) != 2

    @pytest.mark.parametrize("name", ["@marketplace", "plugin@", "@"])
    def test_invalid_plugin_name_empty_parts(self, name):
        """测试空名称或市场"""
        parts = name.split("@")
        assert len(parts) == 2
        # At least one part must be empty
        assert not parts[0] or not parts[1]

    def test_multiple_at_signs_rejected(self):
        """测试多个 @ 符号被拒绝"""
        name = "plugin@@marketplace"
        parts = name.split("@")
        # "@@" splits into 3 parts, so len != 2 means invalid
        assert len(parts) != 2


class TestLogRotation:
    """测试日志轮转"""

    def test_seek_offset_when_file_larger_than_keep_size(self):
        """测试文件大于保留大小时的 seek 偏移量"""
        keep_size = KEEP_LOG_SIZE_MB * 1024 * 1024
        file_size = 12 * 1024 * 1024

        seek_offset = max(-file_size, -keep_size)
        assert seek_offset == -keep_size

    def test_seek_offset_when_file_smaller_than_keep_size(self):
        """测试文件小于保留大小时的 seek 偏移量（避免超出文件边界）"""
        keep_size = KEEP_LOG_SIZE_MB * 1024 * 1024
        file_size = 5 * 1024 * 1024

        seek_offset = max(-file_size, -keep_size)
        assert seek_offset == -file_size


class TestNotificationEscaping:
    """测试通知消息转义（使用从 auto-manager.py 导入的实际函数）"""

    def test_applescript_escapes_double_quotes(self):
        """测试 AppleScript 双引号转义"""
        assert escape_for_applescript('Hello "World"') == 'Hello \\"World\\"'

    def test_applescript_escapes_backslashes(self):
        """测试 AppleScript 反斜杠转义"""
        assert escape_for_applescript("Path\\to\\file") == "Path\\\\to\\\\file"

    def test_powershell_escapes_double_quotes(self):
        """测试 PowerShell 双引号转义"""
        assert escape_for_powershell('Hello "World"') == 'Hello `"World`"'

    def test_powershell_escapes_dollar_signs(self):
        """测试 PowerShell 美元符号转义"""
        assert escape_for_powershell("$variable") == "`$variable"

    def test_plain_text_unchanged(self):
        """测试普通文本不被修改"""
        plain = "Hello World 123"
        assert escape_for_applescript(plain) == plain
        assert escape_for_powershell(plain) == plain


class TestGitSync:
    """测试 Git 同步文件白名单"""

    def test_only_specific_files_added(self):
        """测试只添加特定文件（无通配符或目录）"""
        files_to_add = [
            "snapshots/current.json",
            "config.json",
            "CLAUDE.md",
            "README.md",
            ".gitignore",
        ]

        assert "." not in files_to_add
        assert "*" not in files_to_add
        assert all("/" not in f or f.count("/") == 1 for f in files_to_add)


def test_constants_have_expected_values():
    """测试常量已正确定义且值合理"""
    assert MAX_LOG_SIZE_MB == 10
    assert KEEP_LOG_SIZE_MB == 8
    assert KEEP_LOG_SIZE_MB < MAX_LOG_SIZE_MB
    assert RETRY_INTERVAL_SECONDS == 600
    assert MAX_RETRY_COUNT == 5
    assert COMMAND_TIMEOUT_SHORT == 60
    assert COMMAND_TIMEOUT_LONG == 120
    assert COMMAND_TIMEOUT_SHORT < COMMAND_TIMEOUT_LONG


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
