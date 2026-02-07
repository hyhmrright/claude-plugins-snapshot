# Claude Code 插件自动管理器

自动管理 Claude Code 插件的安装和更新，支持跨机器同步配置。

## ✨ 功能特性

- ✅ **自动安装**：启动时自动安装快照中缺失的插件
- ✅ **自动更新**：每 24 小时自动更新所有插件
- ✅ **Git 同步**：快照自动同步到 GitHub，支持多机器共享
- ✅ **跨平台通知**：更新完成后发送系统通知（macOS/Linux/Windows）
- ✅ **后台执行**：不阻塞 Claude 启动
- ✅ **一键安装**：新机器上运行一个脚本即可完成配置
- ✅ **跨平台支持**：macOS、Linux、Windows、DevContainer

## 🚀 快速开始

### macOS / Linux / DevContainer

```bash
# 1. 克隆仓库到 Claude 插件目录
cd ~/.claude/plugins/
git clone git@github.com:hyhmrright/claude-plugins-snapshot.git auto-manager

# 2. 运行安装脚本（推荐使用 Python 版本）
cd auto-manager
python3 install.py

# 或使用 Bash 脚本（仅 Unix 系统）
# ./install.sh

# 3. 重启 Claude Code
# 插件会自动安装快照中的所有插件
```

### Windows

```powershell
# 1. 克隆仓库到 Claude 插件目录
# 注意：Windows 上 Claude 配置目录可能在 %APPDATA%\Claude
cd %USERPROFILE%\.claude\plugins
git clone git@github.com:hyhmrright/claude-plugins-snapshot.git auto-manager

# 2. 运行 Python 安装脚本
cd auto-manager
python install.py

# 3. 重启 Claude Code
# 插件会自动安装快照中的所有插件
```

就这么简单！🎉

### 首次设置（当前机器）

当前机器已完成设置，快照已同步到 GitHub。

## 📋 工作原理

### 自动化流程

**每次启动 Claude 时**：
1. **安装缺失插件**：对比快照和当前安装，自动安装缺失的插件
2. **定时更新**：检查距离上次更新是否超过 24 小时，如果是则自动更新所有插件
3. **智能同步**：
   - ✅ **插件列表变化**（安装/卸载）→ 生成快照并推送到 Git
   - ❌ **只是版本更新**（自动更新）→ 不推送，避免无意义的 commit

### Git 同步策略

**只在以下情况推送到 GitHub**：
- ✅ 手动安装了新插件
- ✅ 卸载了插件
- ✅ 启动时自动安装了缺失的插件
- ❌ 自动更新（只更新版本号，不改变插件列表）

这样可以避免每天产生大量无意义的 Git commit。

## 📁 目录结构

```
auto-manager/
├── .claude-plugin/
│   └── plugin.json          # 插件元数据
├── hooks/
│   └── hooks.json           # SessionStart Hook 配置
├── scripts/
│   ├── session-start.sh     # Hook 入口（后台执行）
│   ├── auto-manager.py      # 主逻辑（安装 + 更新）
│   ├── create-snapshot.py   # 生成插件快照
│   ├── git-sync.py          # Git 同步脚本
│   ├── sync-snapshot.sh     # 手动同步快照到 Git
│   └── sync-snapshot.py     # 手动同步快照（跨平台）
├── snapshots/
│   ├── current.json         # 当前快照（唯一快照文件）
│   ├── .last-update         # 上次更新时间戳（本地）
│   └── .last-install-state.json  # 安装状态（本地）
├── logs/                    # 运行日志（本地）
│   └── auto-manager.log
├── config.json              # 配置文件
├── install.sh               # 新机器安装脚本
├── .gitignore              # Git 忽略文件
└── README.md               # 本文档
```

## 🔧 常用命令

### ⚠️ 手动安装插件后同步到 Git（必须执行！）

**重要规则**：每次手动安装/卸载插件后，**必须立即**运行同步命令！

#### 如果使用 Claude Code AI 助手

当您告诉 Claude "我安装了新插件"时，Claude 会自动执行以下流程：

1. **运行同步脚本**：
   ```bash
   cd ~/.claude/plugins/auto-manager && python3 scripts/sync-snapshot.py
   ```

2. **验证同步结果**：
   ```bash
   # 查看最新提交
   git log -1 --oneline

   # 确认已推送
   git status -sb

   # 检查插件数量
   cat snapshots/current.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'插件数量: {len(data[\"plugins\"])}')"
   ```

3. **关键路径**：
   - 实际插件目录：`~/.claude/plugins/auto-manager/`
   - Git 仓库：`git@github.com:hyhmrright/claude-plugins-snapshot.git`
   - 快照文件：`~/.claude/plugins/auto-manager/snapshots/current.json`

#### 手动执行同步

如果不使用 Claude，手动运行：

```bash
# 推荐（跨平台）
python3 ~/.claude/plugins/auto-manager/scripts/sync-snapshot.py

# 或使用 Bash 脚本（Unix 系统）
~/.claude/plugins/auto-manager/scripts/sync-snapshot.sh
```

这个命令会：
1. 生成新快照
2. 检测是否有变化
3. 自动提交并推送到 GitHub

### 手动触发更新（不等 24 小时）

```bash
python3 ~/.claude/plugins/auto-manager/scripts/auto-manager.py --force-update
```

### 查看实时日志

```bash
tail -f ~/.claude/plugins/auto-manager/logs/auto-manager.log
```

### 查看快照内容

```bash
cat ~/.claude/plugins/auto-manager/snapshots/current.json
```

## ⚙️ 配置选项

编辑 `config.json` 来自定义行为：

```json
{
  "auto_install": {
    "enabled": true              // 启用/禁用自动安装
  },
  "auto_update": {
    "enabled": true,             // 启用/禁用自动更新
    "interval_hours": 24,        // 更新间隔（小时）
    "notify": true               // 是否发送系统通知
  },
  "git_sync": {
    "enabled": true,             // 是否同步到 Git
    "auto_push": true            // 是否自动推送
  },
  "snapshot": {
    "keep_versions": 10          // 保留快照版本数（已弃用）
  }
}
```

## 📦 快照文件格式

`snapshots/current.json` 是唯一的快照文件，包含所有已安装插件的信息：

```json
{
  "version": "1.0",
  "timestamp": "2026-02-07T03:00:13Z",
  "plugins": {
    "github@claude-plugins-official": {
      "enabled": true,
      "version": "2cd88e7947b7",
      "gitCommitSha": "ee2f726...",
      "marketplace": "claude-plugins-official"
    }
  },
  "marketplaces": {
    "claude-plugins-official": {
      "source": "github",
      "repo": "anthropics/claude-plugins-official",
      "autoUpdate": true
    }
  }
}
```

## 🔄 多机器同步工作流

### 机器 A（安装新插件）

```bash
# 1. 手动安装新插件
claude plugin install some-plugin@marketplace

# 2. 同步到 GitHub（一条命令）
python3 ~/.claude/plugins/auto-manager/scripts/sync-snapshot.py
# ✓ 自动生成快照
# ✓ 自动检测变化
# ✓ 自动提交推送
```

### 机器 B（自动同步）

```bash
# 什么都不用做！

# 下次启动 Claude 时：
# 1. 自动从 Git 拉取最新快照（通过 git pull）
# 2. 自动安装新插件
# 3. 自动更新所有插件（如果距离上次更新超过 24 小时）
```

**注意**：
- ✅ **插件列表变化**才会推送到 Git
- ❌ **日常自动更新**不会推送（避免无意义的 commit）
- 🔄 其他机器会自动拉取并安装新插件

## 🌍 跨平台支持

### 支持的平台

| 平台 | 状态 | 安装脚本 | 通知 | 备注 |
|------|------|---------|------|------|
| macOS | ✅ 完全支持 | `install.py` / `install.sh` | osascript | 原生支持 |
| Linux | ✅ 完全支持 | `install.py` / `install.sh` | notify-send | 需要桌面环境 |
| Windows | ✅ 完全支持 | `install.py` | PowerShell Toast | 推荐使用 Python 脚本 |
| DevContainer | ✅ 完全支持 | `install.py` / `install.sh` | 可能不可用 | 通知功能可选 |
| WSL | ✅ 完全支持 | `install.py` / `install.sh` | 取决于环境 | 按 Linux 处理 |

### 平台差异说明

**Claude 配置目录**：
- macOS/Linux/WSL: `~/.claude`
- Windows: `%APPDATA%\Claude` 或 `~/.claude`
- DevContainer: `~/.claude`（容器内）

**通知系统**：
- macOS: 使用 `osascript` 发送原生通知
- Linux: 使用 `notify-send`（需要安装 libnotify）
- Windows: 使用 PowerShell Toast 通知
- DevContainer: 可能没有桌面环境，通知功能自动跳过

**安装脚本选择**：
- **推荐**：`python3 install.py`（所有平台通用）
- 备选：`./install.sh`（仅 Unix 系统，Windows 需要 Git Bash）

### DevContainer 特殊说明

在 DevContainer 中使用时：

```bash
# 1. 确保 devcontainer.json 中挂载了 Claude 配置
{
  "mounts": [
    "source=${localEnv:HOME}/.claude,target=/home/vscode/.claude,type=bind"
  ]
}

# 2. 在容器内安装
cd ~/.claude/plugins/
git clone git@github.com:hyhmrright/claude-plugins-snapshot.git auto-manager
cd auto-manager
python3 install.py

# 3. 重启 Claude Code（在宿主机上）
```

### Windows 特殊说明

**路径格式**：
```powershell
# PowerShell（推荐）
cd $env:USERPROFILE\.claude\plugins

# CMD
cd %USERPROFILE%\.claude\plugins

# Git Bash
cd ~/.claude/plugins
```

**执行权限**：
Windows 不需要 `chmod +x`，Python 脚本可以直接运行。

**SSH 密钥**：
确保 Git SSH 密钥已配置：
```powershell
# 测试 GitHub 连接
ssh -T git@github.com
```

## ❓ 常见问题

### 如何禁用自动更新？

编辑 `config.json`，将 `auto_update.enabled` 设置为 `false`。

### 如何修改更新频率？

编辑 `config.json`，修改 `auto_update.interval_hours` 的值（单位：小时）。

### 如何查看自动安装/更新的日志？

```bash
tail -f ~/.claude/plugins/auto-manager/logs/auto-manager.log
```

### Git 推送失败怎么办？

检查：
1. SSH 密钥是否配置正确：`ssh -T git@github.com`
2. 远程仓库权限是否正确
3. 网络连接是否正常

即使推送失败，本地 commit 仍会成功，不影响插件管理功能。

### 如何在新机器上使用不同的快照？

1. Fork 这个仓库到你自己的 GitHub
2. 修改 `snapshots/current.json` 为你想要的配置
3. 在新机器上克隆你的 fork：
   ```bash
   git clone git@github.com:你的用户名/仓库名.git ~/.claude/plugins/auto-manager
   ```

### 为什么只有 current.json，没有历史快照？

为了简化 Git 仓库，我们只保留最新的快照。Git 的版本历史已经提供了足够的回溯能力。

### 插件本身会自动更新吗？

不会。这是一个本地插件（`@local`），不会通过 `claude plugin update` 更新。

要更新插件代码：
```bash
cd ~/.claude/plugins/auto-manager
git pull
```

## 🛠️ 故障排查

### 插件未自动安装

1. 检查日志：
   ```bash
   tail ~/.claude/plugins/auto-manager/logs/auto-manager.log
   ```

2. 确认配置：
   ```bash
   cat ~/.claude/plugins/auto-manager/config.json
   ```

3. 手动运行测试：
   ```bash
   python3 ~/.claude/plugins/auto-manager/scripts/auto-manager.py
   ```

### 更新未执行

1. 检查时间戳：
   ```bash
   cat ~/.claude/plugins/auto-manager/snapshots/.last-update
   ```

2. 强制更新：
   ```bash
   python3 ~/.claude/plugins/auto-manager/scripts/auto-manager.py --force-update
   ```

### Hook 未触发

1. 确认插件已启用：
   ```bash
   grep "plugin-auto-manager" ~/.claude/settings.json
   ```

2. 检查 Hook 配置：
   ```bash
   cat ~/.claude/plugins/auto-manager/hooks/hooks.json
   ```

3. 重启 Claude Code

## 📚 相关链接

- **Git 仓库**: https://github.com/hyhmrright/claude-plugins-snapshot
- **Claude Code 文档**: https://docs.anthropic.com/claude-code

## 📝 版本历史

- **1.0.0** (2026-02-07)
  - 初始版本
  - 支持自动安装、自动更新、Git 同步
  - macOS 系统通知
  - 一键安装脚本
  - 简化快照管理（只保留 current.json）

## 📄 许可证

MIT License

---

**需要帮助？** 查看日志文件或提 Issue 到 GitHub 仓库。
