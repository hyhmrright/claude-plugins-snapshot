[English](README.en.md) | 简体中文

# Claude Code 插件自动管理器

自动管理 Claude Code 插件的安装和更新，支持跨机器同步配置。

## ✨ 功能特性

- ✅ **自动安装**：启动时自动安装快照中缺失的插件
- ✅ **智能重试**：安装失败自动重试，10 分钟间隔，最多 5 次
- ✅ **自动更新**：可配置每次启动更新或定时更新（默认：每次启动时更新）
- ✅ **Marketplace 逐个更新**：自动读取所有已知 marketplace 并逐个更新
- ✅ **Git 同步**：快照自动同步到 GitHub，支持多机器共享
- ✅ **仓库自同步**：启动时自动 `git pull` 拉取最新快照和配置
- ✅ **自注册机制**：启动时及插件操作后自动注册，防止 `installed_plugins.json` 被重建导致 Hook 丢失
- ✅ **全局 Hook**：将 Hook 注册到 `~/.claude/settings.local.json`，不依赖 `installed_plugins.json`，从根本上解决 Hook 丢失问题
- ✅ **全局规则同步**：自动同步 `global-rules/CLAUDE.md` 到 `~/.claude/CLAUDE.md`
- ✅ **全局 Skills 同步**：自动同步 `global-skills/` 目录到 `~/.claude/skills/`
- ✅ **跨平台通知**：更新完成后发送系统通知（macOS/Linux/Windows）
- ✅ **后台执行**：不阻塞 Claude 启动
- ✅ **日志管理**：自动轮转，最多保留 10MB
- ✅ **一键安装**：新机器上运行一个脚本即可完成配置
- ✅ **跨平台支持**：macOS、Linux、Windows、DevContainer

## 🚀 快速开始

### 🤖 方式一：Claude AI 助手一键设置（推荐）

**最简单的方式**：在新机器上启动 Claude Code 后，直接告诉 Claude：

> "用 `git@github.com:hyhmrright/claude-plugins-snapshot.git` 设置我的插件"

Claude 会自动执行：
1. ✅ 克隆仓库到 `~/.claude/plugins/auto-manager`
2. ✅ 运行安装脚本
3. ✅ 验证设置成功
4. ✅ 提示您重启 Claude Code

**完全自动化，无需手动操作！** 🎉

---

### 🛠️ 方式二：手动安装

#### macOS / Linux / DevContainer

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

#### SessionStart Hook（会话启动时）

**每次启动 Claude 时**：
1. **备份清理**：自动删除 Claude Code 生成的 `~/.claude.json.backup.<timestamp>` 临时备份文件
2. **自注册检查**：确保 auto-manager 在 `installed_plugins.json` 中注册（防止插件级 Hook 丢失）
3. **全局 Hook 检查**：确保 Hook 在 `~/.claude/settings.local.json` 中注册，并自动修正 `matcher`/`async`/`timeout` 字段
4. **仓库自同步**：`git pull` 拉取最新快照和配置（在加载配置前执行，确保使用远程最新版本）
5. **Marketplace 同步**：将快照中的 marketplace 同步到本地 `known_marketplaces.json`（支持跨机器新增 marketplace）
6. **安装缺失插件**：对比快照和当前安装，自动安装缺失的插件
   - **智能重试**：安装失败后 10 分钟自动重试，最多 5 次
   - **状态记录**：跟踪每个插件的安装状态和重试次数
7. **全局规则同步**：自动同步 `global-rules/CLAUDE.md` 到 `~/.claude/CLAUDE.md`
8. **全局 Skills 同步**：自动同步 `global-skills/` 目录到 `~/.claude/skills/`
9. **自动更新**（可配置）：
   - **默认行为**（`interval_hours: 0`）：每次启动都更新 Marketplaces 和所有插件，确保始终最新
   - **定时更新**（`interval_hours: 24`）：每 24 小时更新一次 Marketplaces 和插件
   - **更新顺序**：先逐个更新 Marketplaces（从 `known_marketplaces.json` 读取），再逐个更新插件
   - **会话检测**：在 Claude Code 会话中自动跳过更新（避免嵌套会话错误）
10. **智能同步**：
    - ✅ **插件列表变化**（安装/卸载）→ 生成快照并推送到 Git
    - ❌ **只是版本更新**（自动更新）→ 不推送，避免无意义的 commit
11. **日志管理**：
   - 自动轮转，最多保留 10MB
   - 超出时保留最近 8MB 内容

### Git 同步策略

**只在以下情况推送到 GitHub**：
- ✅ 启动时检测到插件列表变化（安装/卸载）
- ✅ 启动时自动安装了缺失的插件
- ❌ 自动更新（只更新版本号，不改变插件列表）

这样可以避免每天产生大量无意义的 Git commit。

### 手动安装/卸载插件后的同步

如果在当前会话中安装/卸载了插件，有两种方式同步：

1. **重启 Claude Code**（推荐）：SessionStart hook 会自动检测并同步
2. **手动运行同步命令**（如需立即同步）：
   ```bash
   cd ~/.claude/plugins/auto-manager && python3 scripts/sync-snapshot.py
   ```

## 📁 目录结构

```
auto-manager/
├── .claude-plugin/
│   └── plugin.json          # 插件元数据
├── hooks/
│   └── hooks.json           # SessionStart Hook 配置（插件级，备选）
├── scripts/
│   ├── session-start.sh     # Hook 入口（async:true 由 Claude Code 负责后台化）
│   ├── session-start.py     # Hook 入口备选（Windows）
│   ├── auto-manager.py      # 主逻辑（安装 + 更新）
│   ├── create-snapshot.py   # 生成插件快照
│   ├── git-sync.py          # Git 同步脚本
│   ├── sync-snapshot.sh     # 手动同步快照到 Git
│   └── sync-snapshot.py     # 手动同步快照（跨平台）
├── global-rules/            # 全局规则（Git 追踪，同步到 ~/.claude/CLAUDE.md）
│   └── CLAUDE.md
├── global-skills/           # 全局 Skills（Git 追踪，同步到 ~/.claude/skills/）
│   └── sync-snapshot/
│       └── SKILL.md
├── tests/                   # 测试用例（pytest）
│   └── test_auto_manager.py
├── snapshots/
│   ├── current.json         # 当前快照（唯一快照文件）
│   ├── .last-update         # 上次更新时间戳（本地）
│   └── .last-install-state.json  # 安装状态（本地）
├── logs/                    # 运行日志（本地）
│   └── auto-manager.log
├── config.json              # 配置文件
├── install.py               # 新机器安装脚本（推荐，跨平台）
├── install.sh               # 新机器安装脚本（仅 Unix）
├── .gitignore              # Git 忽略文件
└── README.md               # 本文档
```

## 🔧 常用命令

### 📦 插件同步到 Git

#### 自动同步（推荐）

**SessionStart Hook** 会在每次启动 Claude Code 时自动检测插件变化并同步：

1. **安装/卸载插件后**：重启 Claude Code
2. **系统自动检测**：SessionStart hook 自动运行
3. **智能同步**：只在插件列表有变化时才推送到 GitHub

#### 手动立即同步（可选）

如果不想重启，可以手动运行同步命令：

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

#### 验证同步结果（可选）

```bash
# 查看最新提交
cd ~/.claude/plugins/auto-manager && git log -1 --oneline

# 确认已推送
git status -sb

# 检查插件数量
cat snapshots/current.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'插件数量: {len(data[\"plugins\"])}')"
```

#### 关键路径

- 实际插件目录：`~/.claude/plugins/auto-manager/`
- Git 仓库：`git@github.com:hyhmrright/claude-plugins-snapshot.git`
- 快照文件：`~/.claude/plugins/auto-manager/snapshots/current.json`
- 日志文件：`~/.claude/plugins/auto-manager/logs/auto-manager.log`

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
    "interval_hours": 0,         // 更新间隔（小时）
                                 // 0 = 每次启动都更新
                                 // 24 = 每 24 小时更新一次
    "notify": true               // 是否发送系统通知
  },
  "global_sync": {
    "enabled": true              // 是否同步 global-rules/CLAUDE.md 到 ~/.claude/CLAUDE.md
  },
  "global_skills_sync": {
    "enabled": true              // 是否同步 global-skills/ 到 ~/.claude/skills/
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

**配置说明**：

- `interval_hours: 0` - **每次启动时更新**：每次启动 Claude Code 时都会检查并更新所有插件（推荐）
- `interval_hours: 24` - **每日更新**：每 24 小时更新一次插件
- `interval_hours: N` - **自定义间隔**：每 N 小时更新一次

**智能重试机制**：

插件安装失败后会自动重试，规则如下：
- ⏱️ **重试间隔**：10 分钟
- 🔄 **最大重试**：5 次
- 📊 **状态跟踪**：记录在 `snapshots/.last-install-state.json`
- ⚠️ **超限处理**：5 次失败后暂时放弃，等待下次手动更新

**日志管理**：

- 📁 **日志位置**：`logs/auto-manager.log`
- 📏 **大小限制**：最多 10MB
- ♻️ **自动轮转**：超过 10MB 时保留最近 8MB
- 🔒 **原子操作**：使用临时文件避免损坏

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
# 3. 自动更新所有插件（根据配置，默认：每次启动更新）
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

**可选值**：
- `0` - 每次启动 Claude Code 时都更新（推荐，确保插件始终最新）
- `24` - 每 24 小时更新一次
- 任意数字 - 自定义更新间隔（小时）

**示例**：
```json
{
  "auto_update": {
    "enabled": true,
    "interval_hours": 0,  // 每次启动都更新
    "notify": true
  }
}
```

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

1. 检查全局 Hook 配置：
   ```bash
   cat ~/.claude/settings.local.json | python3 -m json.tool
   ```
   确认 `hooks.SessionStart` 中包含指向 `session-start.sh` 的条目。

2. 修复全局 Hook：
   ```bash
   python3 ~/.claude/plugins/auto-manager/install.py
   # 或
   python3 ~/.claude/plugins/auto-manager/scripts/auto-manager.py
   ```

3. 确认插件已启用（备选 Hook）：
   ```bash
   grep "auto-manager" ~/.claude/settings.json
   ```

4. 重启 Claude Code

## 📚 相关链接

- **Git 仓库**: https://github.com/hyhmrright/claude-plugins-snapshot
- **Claude Code 文档**: https://docs.anthropic.com/claude-code

## 📝 版本历史

- **Unreleased**
  - 全局 Hook：迁移至 `~/.claude/settings.local.json`，不再依赖 `installed_plugins.json`；启动时自动修正旧 hook 的 `matcher`/`async`/`timeout` 字段
  - Hook 执行方式：`async: true` 由 Claude Code 负责后台化，超时 120 秒
  - Hook matcher：使用 `matcher: "startup"` 限制只在新会话启动时触发
  - 启动延迟：10 秒等待 Claude Code 初始化，修复竞态条件
  - 插件更新：跳过本地插件、支持基础名称回退
  - 全局规则同步、全局 Skills 同步
  - 仓库自同步、自注册机制
  - 跳过本地插件（无 `@marketplace` 后缀）的快照和安装
  - 备份清理：自动删除 Claude Code 生成的临时备份文件
- **1.1.0** (2026-02-14)
  - 安全修复：会话检测、通知消息转义、Git 白名单
  - 常量化配置、输入验证、类型提示
  - 测试用例（pytest）
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
