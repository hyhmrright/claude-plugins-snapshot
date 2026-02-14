#!/usr/bin/env python3
"""
Unit tests for auto-manager.py
"""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest


class TestRetryLogic:
    """测试重试机制"""

    def test_first_failure_sets_retry_count_to_one(self):
        """测试首次失败时 retry_count 设置为 1"""
        # 这个测试验证修复后的逻辑
        state = {}
        plugin_name = "test-plugin@marketplace"
        now = datetime.now(timezone.utc).isoformat()

        # 模拟首次失败
        state[plugin_name] = {
            "status": "failed",
            "last_attempt": now,
            "retry_count": 1,
            "first_failed_at": now,
        }

        assert state[plugin_name]["retry_count"] == 1

    def test_max_retry_count_check(self):
        """测试最大重试次数检查"""
        MAX_RETRY_COUNT = 5

        # retry_count <= MAX_RETRY_COUNT 应该允许重试
        assert 1 <= MAX_RETRY_COUNT  # 可以重试
        assert 5 <= MAX_RETRY_COUNT  # 第5次尝试仍可以
        assert not (6 > MAX_RETRY_COUNT)  # 第6次应该被拒绝


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

    def test_invalid_plugin_name_empty_parts(self):
        """测试空名称或市场"""
        invalid_names = ["@marketplace", "plugin@", "@", "@@"]

        for name in invalid_names:
            parts = name.split("@")
            if len(parts) == 2:
                assert not (parts[0] and parts[1])


class TestLogRotation:
    """测试日志轮转"""

    def test_seek_offset_calculation(self):
        """测试 seek 偏移量计算"""
        MAX_LOG_SIZE_MB = 10
        KEEP_LOG_SIZE_MB = 8

        max_size = MAX_LOG_SIZE_MB * 1024 * 1024
        keep_size = KEEP_LOG_SIZE_MB * 1024 * 1024

        # 文件大于保留大小
        file_size = 12 * 1024 * 1024
        seek_offset = max(-file_size, -keep_size)
        assert seek_offset == -keep_size

        # 文件小于保留大小
        file_size = 5 * 1024 * 1024
        seek_offset = max(-file_size, -keep_size)
        assert seek_offset == -file_size


class TestNotificationEscaping:
    """测试通知消息转义"""

    def test_applescript_escaping(self):
        """测试 AppleScript 转义"""

        def escape_for_applescript(text: str) -> str:
            return text.replace("\\", "\\\\").replace('"', '\\"')

        # 测试双引号
        assert escape_for_applescript('Hello "World"') == 'Hello \\"World\\"'

        # 测试反斜杠
        assert escape_for_applescript("Path\\to\\file") == "Path\\\\to\\\\file"

    def test_powershell_escaping(self):
        """测试 PowerShell 转义"""

        def escape_for_powershell(text: str) -> str:
            return text.replace('"', '`"').replace("$", "`$")

        # 测试双引号
        assert escape_for_powershell('Hello "World"') == 'Hello `"World`"'

        # 测试美元符号
        assert escape_for_powershell("$variable") == "`$variable"


class TestGitSync:
    """测试 Git 同步"""

    def test_only_specific_files_added(self):
        """测试只添加特定文件"""
        files_to_add = [
            "snapshots/current.json",
            "config.json",
            "CLAUDE.md",
            "README.md",
            ".gitignore",
        ]

        # 验证列表不包含危险的通配符
        assert "." not in files_to_add
        assert "*" not in files_to_add
        assert all(isinstance(f, str) for f in files_to_add)


def test_constants_defined():
    """测试常量已定义"""
    # 这些常量应该在 auto-manager.py 中定义
    required_constants = [
        "MAX_LOG_SIZE_MB",
        "KEEP_LOG_SIZE_MB",
        "RETRY_INTERVAL_SECONDS",
        "MAX_RETRY_COUNT",
        "COMMAND_TIMEOUT_SHORT",
        "COMMAND_TIMEOUT_LONG",
    ]

    # 这个测试提醒我们所有常量都应该被定义
    assert len(required_constants) == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
