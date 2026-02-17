#!/usr/bin/env python3
"""
生成 Claude Code 插件快照
从 settings.json 和 installed_plugins.json 读取当前配置并保存到快照文件
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def log(message: str) -> None:
    """输出日志消息"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{timestamp}] {message}", flush=True)


def create_snapshot() -> Path:
    """创建插件快照"""
    claude_dir = Path.home() / ".claude"
    snapshot_dir = claude_dir / "plugins" / "auto-manager" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # 读取当前配置
    settings_file = claude_dir / "settings.json"
    installed_file = claude_dir / "plugins" / "installed_plugins.json"
    marketplaces_file = claude_dir / "plugins" / "known_marketplaces.json"

    if not settings_file.exists():
        log("Error: settings.json not found")
        raise FileNotFoundError(f"Settings file not found: {settings_file}")

    if not installed_file.exists():
        log("Error: installed_plugins.json not found")
        raise FileNotFoundError(f"Installed plugins file not found: {installed_file}")

    settings = json.loads(settings_file.read_text())
    installed = json.loads(installed_file.read_text())

    # marketplaces 文件可能不存在
    marketplaces = {}
    if marketplaces_file.exists():
        marketplaces = json.loads(marketplaces_file.read_text())

    # 构建快照
    snapshot = {
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "plugins": {},
        "marketplaces": {},
    }

    # 提取插件信息
    enabled_plugins = settings.get("enabledPlugins", {})
    for plugin_name, enabled in enabled_plugins.items():
        # 跳过本地插件（本地插件不含 @marketplace 后缀）
        if "@" not in plugin_name:
            log(f"Skipping local plugin: {plugin_name}")
            continue

        if plugin_name not in installed.get("plugins", {}):
            continue

        plugin_info_list = installed["plugins"][plugin_name]
        if not plugin_info_list:
            continue

        plugin_info = plugin_info_list[0]  # 取第一个版本

        # 解析 marketplace 名称
        parts = plugin_name.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            log(f"Warning: Invalid plugin name format: {plugin_name}")
            marketplace = "unknown"
        else:
            marketplace = parts[1]

        snapshot["plugins"][plugin_name] = {
            "enabled": enabled,
            "version": plugin_info.get("version", "unknown"),
            "scope": plugin_info.get("scope", "user"),
            "marketplace": marketplace,
        }

        # 添加 Git commit SHA（如果存在）
        if "gitCommitSha" in plugin_info:
            snapshot["plugins"][plugin_name]["gitCommitSha"] = plugin_info[
                "gitCommitSha"
            ]

    # 提取市场源信息
    for name, config in marketplaces.items():
        if "source" in config and isinstance(config["source"], dict):
            snapshot["marketplaces"][name] = {
                "source": config["source"].get("source", "unknown"),
                "repo": config["source"].get("repo", "unknown"),
                "autoUpdate": config.get("autoUpdate", False),
            }

    # 直接保存为 current.json（不创建历史快照）
    current_file = snapshot_dir / "current.json"
    current_file.write_text(json.dumps(snapshot, indent=2) + "\n")

    log("Snapshot updated: current.json")
    log(f"Total plugins: {len(snapshot['plugins'])}")

    return current_file


if __name__ == "__main__":
    try:
        snapshot_file = create_snapshot()
        print(f"\n✓ Snapshot saved to: {snapshot_file.parent / 'current.json'}")
    except Exception as e:
        log(f"Error creating snapshot: {e}")
        import sys

        sys.exit(1)
