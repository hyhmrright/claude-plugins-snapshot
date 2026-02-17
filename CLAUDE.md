[English](CLAUDE.en.md) | 简体中文

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个 Claude Code 插件自动管理器（Plugin Auto-Manager），通过 SessionStart Hook 实现插件的自动安装、更新和跨机器同步。这是一个本地插件（`@local`），部署在 `~/.claude/plugins/auto-manager/`。

**当前版本**: v1.1.0（2026-02-14）- 包含重要安全修复和代码质量改进

## 核心架构

### 三层自动化架构

1. **Hook 层** （双重保障）
   - **全局 Hook**（主要）：注册在 `~/.claude/settings.local.json`，不依赖 `installed_plugins.json`，始终触发
   - **插件 Hook**（备选）：`hooks/hooks.json`，依赖插件注册，作为向后兼容保留
   - 两者均使用 `matcher: "startup"` 限制只在新会话启动时触发（不在 resume/clear/compact 时触发）
   - 两者均调用 `scripts/session-start.sh` 在后台执行（避免阻塞启动），延迟 10 秒等待 Claude Code 完成初始化
   - `scripts/session-start.py` 提供 Windows 备选入口（需在 `install.py` 中配置）
   - 超时设置：30秒

2. **管理层** (`scripts/auto-manager.py`)
   - **主逻辑**：协调安装、更新、同步三大功能
   - **智能重试**：安装失败后 10 分钟自动重试，最多 5 次，状态记录在 `.last-install-state.json`
   - **会话检测**：自动检测是否在 Claude Code 会话中运行（检查 `CLAUDECODE` 环境变量）避免嵌套会话错误
   - **仓库自同步**：启动时自动 `git pull` 拉取最新快照和配置
   - **自注册机制**：启动时及每次插件安装/更新后，确保自身在 `installed_plugins.json` 中注册，防止被 Claude Code 重建文件导致 Hook 丢失
   - **全局 Hook 保障**：将 SessionStart Hook 注册到 `~/.claude/settings.local.json`，不依赖 `installed_plugins.json`，从根本上解决 Hook 丢失的死循环问题
   - **Marketplace 逐个更新**：读取 `known_marketplaces.json` 逐个更新所有 marketplace（含名称验证）
   - **定时更新**：根据 `config.json` 中的 `interval_hours` 配置（0=每次启动，24=每日更新）
   - **日志管理**：自动轮转，超过 10MB 时截断到 8MB
   - **备份清理**：每次启动时自动删除 Claude Code 生成的 `~/.claude.json.backup.<timestamp>` 备份文件，只保留主备份文件
   - **全局规则同步**：将仓库中的全局规则自动同步到 `~/.claude/CLAUDE.md`
   - **常量化配置**：所有魔术数字已提取为常量（v1.1.0）

3. **工具层**
   - `create-snapshot.py`：从 Claude 配置文件生成快照（含输入验证）
   - `git-sync.py`：将快照同步到 Git 仓库（仅添加特定文件）
   - `sync-snapshot.py`：手动触发快照同步（跨平台）

### 关键常量（v1.1.0 新增）

所有配置常量在 `scripts/auto-manager.py` 顶部定义：

```python
# 配置路径
KNOWN_MARKETPLACES_FILE = CLAUDE_DIR / "plugins" / "known_marketplaces.json"

# 日志管理
MAX_LOG_SIZE_MB = 10           # 日志最大大小
KEEP_LOG_SIZE_MB = 8           # 轮转后保留大小

# 重试机制
RETRY_INTERVAL_SECONDS = 600   # 重试间隔（10分钟）
MAX_RETRY_COUNT = 5            # 最大重试次数

# 超时时间（秒）
COMMAND_TIMEOUT_SHORT = 60     # Git 操作、快照创建
COMMAND_TIMEOUT_LONG = 120     # 插件安装/更新
```

**修改常量时注意**：需要同时更新代码中的引用和测试用例

### 关键数据文件

```
snapshots/
├── current.json              # 唯一快照文件（Git 追踪）
├── .last-update              # 上次更新时间戳（本地，Git 忽略）
└── .last-install-state.json  # 安装重试状态（本地，Git 忽略）

global-rules/
└── CLAUDE.md                 # 全局规则文件（Git 追踪，同步到 ~/.claude/CLAUDE.md）

global-skills/
└── sync-snapshot/
    └── SKILL.md              # Skill 文件（Git 追踪，同步到 ~/.claude/skills/sync-snapshot/）

logs/
└── auto-manager.log          # 运行日志（本地，Git 忽略）
```

### 智能 Git 同步策略

**只在以下情况推送到 GitHub**：
- ✅ 启动时检测到插件列表变化（新增/删除插件）
- ✅ 启动时自动安装了缺失的插件
- ❌ 仅版本更新（自动更新插件版本）不推送

**实现原理**：
- 对比当前快照和新生成快照的插件键集合（`set(plugins.keys())`）
- 相同 → 跳过推送（只是版本号变化）
- 不同 → 生成快照并推送（插件列表发生变化）

## 常用命令

### 开发和测试

```bash
# 手动运行管理器（测试安装和更新逻辑）
python3 scripts/auto-manager.py

# 强制更新所有插件（忽略时间间隔）
python3 scripts/auto-manager.py --force-update

# 手动生成快照
python3 scripts/create-snapshot.py

# 手动同步快照到 Git（推荐，跨平台）
python3 scripts/sync-snapshot.py

# 或使用 Bash 脚本（仅 Unix 系统）
./scripts/sync-snapshot.sh

# 查看实时日志
tail -f logs/auto-manager.log

# 查看当前快照
cat snapshots/current.json | python3 -m json.tool

# 查看安装重试状态
cat snapshots/.last-install-state.json | python3 -m json.tool
```

### 运行测试（v1.1.0 新增）

```bash
# 安装依赖（使用 uv 管理）
uv sync

# 运行所有测试
uv run pytest tests/ -v

# 运行特定测试文件
uv run pytest tests/test_auto_manager.py -v

# 查看代码覆盖率
uv run pytest tests/ --cov=scripts --cov-report=html
# 然后打开 htmlcov/index.html 查看报告

# 只运行特定测试类
uv run pytest tests/test_auto_manager.py::TestRetryLogic -v
```

### 部署到新机器

```bash
# 1. 克隆仓库到 Claude 插件目录
cd ~/.claude/plugins/
git clone git@github.com:hyhmrright/claude-plugins-snapshot.git auto-manager

# 2. 运行安装脚本（跨平台）
cd auto-manager
python3 install.py

# 3. 重启 Claude Code
# SessionStart Hook 会自动安装快照中的所有插件
```

### Git 操作

```bash
# 查看 Git 状态（在 auto-manager 目录下）
git status

# 查看最近提交
git log -1 --oneline

# 手动拉取最新快照
git pull

# 查看插件数量
cat snapshots/current.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'插件数量: {len(data[\"plugins\"])}')"
```

## 配置文件说明

### `config.json` 结构

```json
{
  "version": "1.0",          // v1.1.0 新增：配置文件版本号
  "auto_install": {
    "enabled": true          // 启用/禁用自动安装缺失插件
  },
  "auto_update": {
    "enabled": true,         // 启用/禁用自动更新
    "interval_hours": 0,     // 更新间隔（小时）
                             // 0 = 每次启动都更新
                             // 24 = 每 24 小时更新一次
    "notify": true           // 是否发送系统通知（macOS/Linux/Windows）
  },
  "global_sync": {
    "enabled": true          // 是否将 global-rules/CLAUDE.md 同步到 ~/.claude/CLAUDE.md
  },
  "global_skills_sync": {
    "enabled": true          // 是否将 global-skills/ 同步到 ~/.claude/skills/
  },
  "git_sync": {
    "enabled": true,         // 是否启用 Git 同步
    "auto_push": true        // 是否自动推送到远程
  },
  "snapshot": {
    "keep_versions": 10      // 历史字段，当前未使用
  }
}
```

### `snapshots/current.json` 结构

```json
{
  "version": "1.0",
  "timestamp": "2026-02-14T03:00:13Z",
  "plugins": {
    "plugin-name@marketplace": {
      "enabled": true,
      "version": "commit-sha-or-version",
      "marketplace": "marketplace-name",
      "gitCommitSha": "full-commit-sha"  // 可选
    }
  },
  "marketplaces": {
    "marketplace-name": {
      "source": "github",
      "repo": "owner/repo",
      "autoUpdate": true
    }
  }
}
```

## 工作原理

### SessionStart Hook 执行流程

1. **触发时机**：每次启动 Claude Code 时
2. **启动延迟**：后台等待 10 秒，让 Claude Code 完成初始化（避免竞态条件导致 `claude plugin update` 因插件系统未就绪而失败）
3. **备份清理**：自动删除 Claude Code 生成的带时间戳的配置备份文件
   - 删除 `~/.claude.json.backup.<timestamp>` 格式的文件
   - 保留 `~/.claude.json.backup`（主备份文件）
   - 目的：防止备份文件无限累积占用磁盘空间
4. **自注册检查**：确保 auto-manager 在 `installed_plugins.json` 中注册
   - 防止被 Claude Code 插件操作重建文件时覆盖
   - 丢失注册信息会导致插件级别 Hook 不再被触发
5. **全局 Hook 检查**：确保 SessionStart Hook 在 `~/.claude/settings.local.json` 中注册
   - 不依赖 `installed_plugins.json`，始终触发
   - 从根本上解决 Hook 丢失的死循环问题
6. **仓库自同步**：`git pull --ff-only` 拉取最新快照和配置
   - 在 `load_config()` 之前执行，确保使用远程最新配置
   - 不受 `git_sync.enabled` 控制（只读操作且配置尚未加载）
7. **会话检测**：检查 `CLAUDECODE` 环境变量
   - 如果在 Claude Code 会话中 → 跳过更新（避免嵌套会话错误）
   - 如果不在会话中 → 正常执行
   - `session-start.sh` 在启动后台进程前会 unset 此变量
8. **安装缺失插件**：
   - 读取 `snapshots/current.json` 中的插件列表
   - 对比 `~/.claude/plugins/installed_plugins.json` 中的已安装列表
   - 安装缺失的插件
   - 失败时记录到 `.last-install-state.json` 供后续重试
   - **安装后重新注册自身**（`claude plugin install` 会重建 `installed_plugins.json`）
9. **全局规则同步**：
   - 读取 `global-rules/CLAUDE.md`
   - 对比 `~/.claude/CLAUDE.md` 内容
   - 有变化 → 更新目标文件
   - 无变化 → 跳过
10. **全局 Skills 同步**：
    - 遍历 `global-skills/` 下的每个子目录
    - 读取 `SKILL.md` 并对比 `~/.claude/skills/<name>/SKILL.md` 内容
    - 有变化 → 更新目标文件
    - 无变化 → 跳过
11. **智能重试**：
    - 读取 `.last-install-state.json` 中的失败记录
    - 检查是否超过 10 分钟重试间隔
    - 重试次数未超过 5 次 → 重试安装
    - 超过 5 次 → 暂时放弃，等待手动干预
12. **定时更新**（可配置）：
    - 检查 `.last-update` 时间戳
    - 如果距离上次更新超过 `interval_hours` → 执行更新
    - `interval_hours: 0` → 每次启动都更新
13. **更新流程**：
    - 先逐个更新 Marketplaces（`claude plugin marketplace update <name>`）
    - 从 `~/.claude/plugins/known_marketplaces.json` 读取所有 marketplace
    - 再逐个更新所有已安装插件（`claude plugin update <name>`）
    - **更新后重新注册自身**（`claude plugin update` 会重建 `installed_plugins.json`）
14. **Git 同步**：
    - 生成新快照
    - 对比插件列表是否变化
    - 有变化 → commit 并 push
    - 无变化 → 跳过（只是版本号更新）
15. **系统通知**（可配置）：
    - macOS：使用 `osascript`
    - Linux：使用 `notify-send`
    - Windows：使用 PowerShell Toast

### 重试机制详解

**状态文件格式** (`.last-install-state.json`):
```json
{
  "plugin-name@marketplace": {
    "last_attempt": "2026-02-14T03:00:13Z",
    "retry_count": 2,
    "error": "Installation failed: timeout"
  }
}
```

**重试逻辑**（v1.1.0 修复）：
- 每次启动时检查所有失败的插件
- 计算距离上次尝试的时间
- **首次失败**：`retry_count = 1`（v1.1.0 修复：之前错误地设为 0）
- 如果 `now - last_attempt >= RETRY_INTERVAL_SECONDS` 且 `retry_count <= MAX_RETRY_COUNT`：
  - 重试安装
  - 成功 → 从状态文件移除
  - 失败 → 增加 `retry_count`
- 如果 `retry_count > MAX_RETRY_COUNT` → 跳过，记录警告日志

## 跨平台支持

### 支持的平台

| 平台 | 状态 | Claude 配置目录 | 安装脚本 | 通知系统 |
|------|------|----------------|---------|---------|
| macOS | ✅ | `~/.claude` | `install.py` / `install.sh` | `osascript` |
| Linux | ✅ | `~/.claude` | `install.py` / `install.sh` | `notify-send` |
| Windows | ✅ | `%APPDATA%\Claude` 或 `~/.claude` | `install.py` | PowerShell Toast |
| WSL | ✅ | `~/.claude` | `install.py` / `install.sh` | 取决于环境 |
| DevContainer | ✅ | `~/.claude` | `install.py` / `install.sh` | 可能不可用 |

### 平台特定注意事项

**Windows**:
- 推荐使用 `install.py`（PowerShell 或 CMD 均可）
- 路径使用 `%USERPROFILE%\.claude\plugins` 或 `$env:USERPROFILE\.claude\plugins`
- 不需要 `chmod +x`，Python 脚本可直接运行

**DevContainer**:
- 需要在 `devcontainer.json` 中挂载 Claude 配置目录
- 系统通知可能不可用（无桌面环境）

**macOS/Linux**:
- 优先使用 `install.py`（更好的跨平台兼容性）
- `install.sh` 作为备选（纯 Bash）

## 日志管理

**日志轮转策略**：
- 最大大小：10MB
- 轮转时保留：8MB（最近的日志）
- 实现方式：原子操作（使用临时文件）
- 失败处理：日志轮转失败不影响主流程

**日志格式**：
```
[2026-02-14T03:00:13Z] 日志消息
```

## 故障排查

### 插件未自动安装

1. 检查日志：`tail -f logs/auto-manager.log`
2. 检查配置：`cat config.json`
3. 检查插件是否启用：`grep "auto-manager" ~/.claude/settings.json`
4. 手动测试：`python3 scripts/auto-manager.py`
5. 检查重试状态：`cat snapshots/.last-install-state.json`

### 更新未执行

1. 检查时间戳：`cat snapshots/.last-update`
2. 检查配置：`cat config.json | grep interval_hours`
3. 强制更新：`python3 scripts/auto-manager.py --force-update`
4. 检查会话环境：`echo $CLAUDECODE`（应为空）

### Git 推送失败

1. 检查 SSH：`ssh -T git@github.com`
2. 检查远程仓库：`git remote -v`
3. 手动推送：`cd snapshots && git push`
4. 检查权限：确保对仓库有写权限

### Hook 未触发

1. **检查全局 Hook**：`cat ~/.claude/settings.local.json | python3 -m json.tool`
   - 确认 `hooks.SessionStart` 中包含指向 `session-start.sh` 的条目
   - 修复：运行 `python3 install.py` 或 `python3 scripts/auto-manager.py`（会自动配置全局 Hook）
2. **检查插件级别 Hook**（备选）：`auto-manager` 未在 `installed_plugins.json` 中注册（被 `claude plugin install/update` 重建文件时覆盖）
   - 检查：`python3 -c "import json; d=json.load(open('$HOME/.claude/plugins/installed_plugins.json')); print('auto-manager' in d.get('plugins', {}))"`
   - 修复：运行 `python3 scripts/auto-manager.py`（会自动重新注册），或运行 `python3 install.py`
3. 检查插件启用状态：`cat ~/.claude/settings.json | grep enabledPlugins`
4. 重启 Claude Code
5. 查看启动日志：`tail -f logs/auto-manager.log`

## 代码修改注意事项

### 修改 Python 脚本时

1. **保持跨平台兼容**：使用 `Path` 而非字符串路径，避免硬编码路径分隔符
2. **保持向后兼容**：修改配置格式时提供默认值
3. **错误处理**：重要操作失败不应中断整个流程（例如日志轮转失败）
4. **原子操作**：修改配置文件时使用临时文件避免损坏
5. **使用常量**：不要硬编码魔术数字，使用文件顶部定义的常量（v1.1.0）
6. **类型提示**：为新函数添加完整的类型提示 `typing.Dict[str, Any]` 等（v1.1.0）
7. **文档字符串**：包含参数和返回值说明（v1.1.0）
8. **输入验证**：验证所有外部输入（插件名格式、配置值等）（v1.1.0）
9. **安全性**：
   - 转义所有传递给 shell 的字符串（防止命令注入）
   - 使用 UTC 时间戳（避免时区问题）
   - Git 操作只添加特定文件，不使用 `git add .`

### 修改 Hook 配置时

1. **避免阻塞**：SessionStart Hook 必须在后台执行（`&`）
2. **超时设置**：Hook 超时应足够长（当前 30 秒），但不宜过长
3. **日志重定向**：所有输出重定向到 `logs/auto-manager.log`
4. **不要改 Hook 入口为 `python3`**：Claude Code Hook 执行环境的 `PATH` 可能不包含 `python3`，必须使用 `.sh` 脚本直接执行（通过 shebang 调用 bash）

### 修改快照格式时

1. **保持版本号**：`version: "1.0"` 用于未来兼容性检查
2. **向后兼容**：新增字段使用可选字段（带默认值）
3. **Git 友好**：保持 JSON 格式一致（缩进 2 空格）

### 添加新功能时

1. **编写测试**：在 `tests/` 目录添加对应的测试用例（v1.1.0）
2. **更新文档**：同时更新 CLAUDE.md、CLAUDE.en.md、README.md、README.en.md（中英文各两个文件，共四个）
3. **更新 CHANGELOG**：记录到 CHANGELOG.md 的 Unreleased 部分
4. **代码审查**：运行 `pytest tests/ -v` 确保所有测试通过
5. **部署验证**：修改 Hook 入口或注册机制等关键路径时，必须在部署环境（`~/.claude/plugins/auto-manager/`）实际启动 Claude Code 验证，单元测试不够
6. **新增同步功能**：复用已有同步函数模式（如 `sync_global_skills()` 参照 `sync_global_rules()`），包含：外层 try-except、内容变化检测、原子写入、日志输出
7. **跨机器同步的文件**：应放在仓库目录（如 `global-skills/`）而非 `~/.claude/` 下，由 auto-manager 负责同步到目标位置

### 重要安全修复（v1.1.0）

1. **会话检测环境变量**：必须使用 `CLAUDECODE`（已确认为 claude CLI 实际使用的变量；v1.1.0 曾错误地改为 `CLAUDE_CODE_SESSION_ID`，已在后续版本修正）
2. **通知消息转义**：
   - macOS: `escape_for_applescript()` - 转义 `\` 和 `"`
   - Windows: `escape_for_powershell()` - 转义 `"` 和 `$`
3. **Git 安全**：只添加白名单文件，防止敏感数据泄露
4. **文件权限**：脚本权限使用 `0o744`（不是 `0o755`）

## Git 仓库说明

- **仓库位置**：`git@github.com:hyhmrright/claude-plugins-snapshot.git`
- **部署路径**：`~/.claude/plugins/auto-manager/`（活跃部署，Claude Code 实际执行）
- **开发路径**：`~/code/claude-plugins-snapshot/`（开发工作区，push 后部署目录下次启动自动 pull）
- **追踪文件**：
  - 配置：`config.json`, `.gitignore`
  - 文档：`CLAUDE.md`, `README.md`, `CHANGELOG.md`, `LICENSE`
  - 代码：`scripts/`, `hooks/`, `.claude/hooks/`, `install.py`, `install.sh`
  - 快照：`snapshots/current.json`
  - 测试：`tests/` （v1.1.0 新增）
  - Skills：`global-skills/`
- **忽略文件**：`logs/`, `snapshots/.last-update`, `snapshots/.last-install-state.json`, `.claude/settings.local.json`
- **Git 同步策略**（v1.1.0 安全增强）：
  - 白名单模式：只添加特定文件到 Git
  - 防止敏感数据泄露（.env, credentials, 私钥等）

## 多机器同步工作流

### 机器 A（安装新插件）
1. 手动安装：`claude plugin install plugin-name@marketplace`
2. 同步快照：`python3 ~/.claude/plugins/auto-manager/scripts/sync-snapshot.py`
   - 自动生成快照
   - 检测插件列表变化
   - commit 并 push 到 GitHub

### 机器 B（自动同步）
1. 下次启动 Claude Code 时：
   - SessionStart Hook 自动触发
   - 从 Git 拉取最新快照（如果启用了 auto_pull）
   - 检测并安装缺失的插件
   - 根据配置决定是否更新插件
