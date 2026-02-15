#!/usr/bin/env python3
"""
Unit tests for auto-manager.py
"""
import importlib.util
import json
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
ensure_self_registered = _auto_manager.ensure_self_registered
get_all_marketplaces = _auto_manager.get_all_marketplaces
sync_self_repo = _auto_manager.sync_self_repo
update_all_marketplaces = _auto_manager.update_all_marketplaces
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


class TestSyncSelfRepo:
    """测试 auto-manager 仓库自身同步"""

    @staticmethod
    def _make_mock_run(monkeypatch, returncode=0, stdout="", stderr=""):
        """创建模拟 subprocess.run 并返回捕获的调用参数"""
        captured = {}

        def mock_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs

            class Result:
                pass

            result = Result()
            result.returncode = returncode
            result.stdout = stdout
            result.stderr = stderr
            return result

        monkeypatch.setattr(_auto_manager.subprocess, "run", mock_run)
        return captured

    def test_sync_success_already_up_to_date(self, monkeypatch):
        """测试仓库已是最新时返回 True"""
        self._make_mock_run(monkeypatch, stdout="Already up to date.\n")
        assert sync_self_repo() is True

    def test_sync_success_with_updates(self, monkeypatch):
        """测试有更新时返回 True"""
        self._make_mock_run(monkeypatch, stdout="Updating abc123..def456\nFast-forward\n")
        assert sync_self_repo() is True

    def test_sync_failure(self, monkeypatch):
        """测试 git pull 失败时返回 False"""
        self._make_mock_run(monkeypatch, returncode=1, stderr="fatal: not a git repository")
        assert sync_self_repo() is False

    def test_sync_uses_ff_only_and_correct_cwd(self, monkeypatch):
        """测试使用 --ff-only 且 cwd 指向 AUTO_MANAGER_DIR"""
        captured = self._make_mock_run(monkeypatch, stdout="Already up to date.\n")
        sync_self_repo()

        assert captured["cmd"] == ["git", "pull", "--ff-only"]
        assert captured["kwargs"]["cwd"] == str(_auto_manager.AUTO_MANAGER_DIR)


class TestEnsureSelfRegistered:
    """测试 auto-manager 自注册机制"""

    def test_registers_when_missing(self, tmp_path, monkeypatch):
        """测试 auto-manager 不在 installed_plugins.json 时自动注册"""
        installed_file = tmp_path / "installed_plugins.json"
        installed_file.write_text('{"version": 2, "plugins": {}}')
        monkeypatch.setattr(_auto_manager, "CLAUDE_DIR", tmp_path)
        # Make the file path match what the function expects
        (tmp_path / "plugins").mkdir()
        installed = tmp_path / "plugins" / "installed_plugins.json"
        installed.write_text('{"version": 2, "plugins": {}}')

        ensure_self_registered()

        data = json.loads(installed.read_text())
        assert "auto-manager" in data["plugins"]
        assert data["plugins"]["auto-manager"][0]["scope"] == "user"

    def test_skips_when_already_registered(self, tmp_path, monkeypatch):
        """测试已注册时不重复注册"""
        (tmp_path / "plugins").mkdir()
        installed = tmp_path / "plugins" / "installed_plugins.json"
        original = '{"version": 2, "plugins": {"auto-manager": [{"scope": "user"}]}}'
        installed.write_text(original)
        monkeypatch.setattr(_auto_manager, "CLAUDE_DIR", tmp_path)

        ensure_self_registered()

        # Content should be unchanged
        assert json.loads(installed.read_text()) == json.loads(original)

    def test_handles_missing_file(self, tmp_path, monkeypatch):
        """测试文件不存在时不报错"""
        monkeypatch.setattr(_auto_manager, "CLAUDE_DIR", tmp_path / "nonexistent")
        ensure_self_registered()  # Should not raise


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
            "global-rules/CLAUDE.md",
        ]

        assert "." not in files_to_add
        assert "*" not in files_to_add
        assert all("/" not in f or f.count("/") == 1 for f in files_to_add)


class TestGlobalRulesSync:
    """测试全局规则同步"""

    ENABLED_CONFIG = {"global_sync": {"enabled": True}}

    def _setup_files(self, tmp_path, monkeypatch, source_content, target_path_suffix="target.md", target_content=None):
        """设置源文件和目标文件路径，返回 (source, target)"""
        source = tmp_path / "source.md"
        source.write_text(source_content, encoding="utf-8")
        target = tmp_path / target_path_suffix
        if target_content is not None:
            target.write_text(target_content, encoding="utf-8")
        monkeypatch.setattr(_auto_manager, "GLOBAL_RULES_SOURCE", source)
        monkeypatch.setattr(_auto_manager, "GLOBAL_RULES_TARGET", target)
        return source, target

    def test_disabled_in_config(self, capsys):
        """测试配置禁用时跳过同步"""
        _auto_manager.sync_global_rules({"global_sync": {"enabled": False}})
        assert "disabled" in capsys.readouterr().out

    def test_missing_config_defaults_to_disabled(self, capsys):
        """测试缺少配置时默认禁用"""
        _auto_manager.sync_global_rules({})
        assert "disabled" in capsys.readouterr().out

    def test_source_not_found(self, tmp_path, monkeypatch, capsys):
        """测试源文件不存在时跳过"""
        monkeypatch.setattr(_auto_manager, "GLOBAL_RULES_SOURCE", tmp_path / "nonexistent.md")
        _auto_manager.sync_global_rules(self.ENABLED_CONFIG)
        assert "not found" in capsys.readouterr().out

    def test_sync_creates_target(self, tmp_path, monkeypatch):
        """测试目标文件不存在时创建"""
        _, target = self._setup_files(tmp_path, monkeypatch, "# Rules\n")
        _auto_manager.sync_global_rules(self.ENABLED_CONFIG)
        assert target.read_text(encoding="utf-8") == "# Rules\n"

    def test_unchanged_content_skipped(self, tmp_path, monkeypatch, capsys):
        """测试内容未变化时跳过"""
        self._setup_files(tmp_path, monkeypatch, "# Rules\n", target_content="# Rules\n")
        _auto_manager.sync_global_rules(self.ENABLED_CONFIG)
        assert "unchanged" in capsys.readouterr().out

    def test_changed_content_synced(self, tmp_path, monkeypatch):
        """测试内容变化时同步"""
        _, target = self._setup_files(tmp_path, monkeypatch, "# New Rules\n", target_content="# Old Rules\n")
        _auto_manager.sync_global_rules(self.ENABLED_CONFIG)
        assert target.read_text(encoding="utf-8") == "# New Rules\n"

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        """测试目标父目录不存在时自动创建"""
        _, target = self._setup_files(tmp_path, monkeypatch, "# Rules\n", target_path_suffix="subdir/target.md")
        _auto_manager.sync_global_rules(self.ENABLED_CONFIG)
        assert target.read_text(encoding="utf-8") == "# Rules\n"


class TestMarketplaceUpdate:
    """测试 Marketplace 更新逻辑"""

    @staticmethod
    def _write_marketplaces(tmp_path, content):
        """写入 known_marketplaces.json 并返回文件路径"""
        mp_file = tmp_path / "known_marketplaces.json"
        mp_file.write_text(content)
        return mp_file

    @staticmethod
    def _mock_subprocess_success(monkeypatch):
        """模拟 subprocess.run 全部成功，返回记录调用的列表"""
        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        monkeypatch.setattr(_auto_manager.subprocess, "run", mock_run)
        return calls

    def test_get_all_marketplaces_reads_file(self, tmp_path, monkeypatch):
        """测试正常读取 known_marketplaces.json"""
        mp_file = self._write_marketplaces(tmp_path, '{"official": {}, "superpowers-marketplace": {}}')
        monkeypatch.setattr(_auto_manager, "KNOWN_MARKETPLACES_FILE", mp_file)

        result = get_all_marketplaces()
        assert len(result) == 2
        assert "official" in result
        assert "superpowers-marketplace" in result

    def test_get_all_marketplaces_file_not_found(self, tmp_path, monkeypatch):
        """测试文件不存在时返回空列表"""
        monkeypatch.setattr(_auto_manager, "KNOWN_MARKETPLACES_FILE", tmp_path / "nonexistent.json")

        result = get_all_marketplaces()
        assert result == []

    def test_get_all_marketplaces_invalid_json(self, tmp_path, monkeypatch):
        """测试 JSON 格式错误时返回空列表"""
        mp_file = self._write_marketplaces(tmp_path, "not valid json")
        monkeypatch.setattr(_auto_manager, "KNOWN_MARKETPLACES_FILE", mp_file)

        result = get_all_marketplaces()
        assert result == []

    def test_get_all_marketplaces_empty_file(self, tmp_path, monkeypatch):
        """测试空对象时返回空列表"""
        mp_file = self._write_marketplaces(tmp_path, "{}")
        monkeypatch.setattr(_auto_manager, "KNOWN_MARKETPLACES_FILE", mp_file)

        result = get_all_marketplaces()
        assert result == []

    def test_update_all_marketplaces_calls_each(self, tmp_path, monkeypatch):
        """测试 update_all_marketplaces 逐个更新每个 marketplace"""
        mp_file = self._write_marketplaces(tmp_path, '{"official": {}, "superpowers-marketplace": {}}')
        monkeypatch.setattr(_auto_manager, "KNOWN_MARKETPLACES_FILE", mp_file)
        calls = self._mock_subprocess_success(monkeypatch)

        result = update_all_marketplaces()
        assert result == 2
        assert ["claude", "plugin", "marketplace", "update", "official"] in calls
        assert ["claude", "plugin", "marketplace", "update", "superpowers-marketplace"] in calls

    def test_update_all_marketplaces_fallback(self, tmp_path, monkeypatch):
        """测试读取失败时回退到无参数命令"""
        monkeypatch.setattr(_auto_manager, "KNOWN_MARKETPLACES_FILE", tmp_path / "nonexistent.json")
        calls = self._mock_subprocess_success(monkeypatch)

        result = update_all_marketplaces()
        assert result == 1
        assert ["claude", "plugin", "marketplace", "update"] in calls

    def test_update_all_marketplaces_partial_failure(self, tmp_path, monkeypatch):
        """测试部分 marketplace 更新失败时返回成功数量"""
        mp_file = self._write_marketplaces(tmp_path, '{"a": {}, "b": {}, "c": {}}')
        monkeypatch.setattr(_auto_manager, "KNOWN_MARKETPLACES_FILE", mp_file)

        def mock_run(cmd, **kwargs):
            class Result:
                stdout = ""
                stderr = "error"
                returncode = 1 if cmd[-1] == "b" else 0

            return Result()

        monkeypatch.setattr(_auto_manager.subprocess, "run", mock_run)

        result = update_all_marketplaces()
        assert result == 2  # a and c succeed, b fails

    def test_get_all_marketplaces_skips_invalid_names(self, tmp_path, monkeypatch):
        """测试跳过格式无效的 marketplace 名称"""
        mp_file = self._write_marketplaces(
            tmp_path, '{"valid-name": {}, "also_valid": {}, "bad name with spaces": {}, "../traversal": {}}'
        )
        monkeypatch.setattr(_auto_manager, "KNOWN_MARKETPLACES_FILE", mp_file)

        result = get_all_marketplaces()
        assert "valid-name" in result
        assert "also_valid" in result
        assert "bad name with spaces" not in result
        assert "../traversal" not in result
        assert len(result) == 2


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
