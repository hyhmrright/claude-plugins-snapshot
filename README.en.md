English | [简体中文](README.md)

# Claude Code Plugin Auto-Manager

Automatically manage Claude Code plugin installation and updates, with cross-machine configuration sync.

## ✨ Features

- ✅ **Auto Install**: Automatically install missing plugins from snapshot on startup
- ✅ **Smart Retry**: Auto-retry failed installations, 10-minute interval, up to 5 attempts
- ✅ **Auto Update**: Configurable update on every startup or on a schedule (default: every startup)
- ✅ **Per-marketplace Updates**: Reads all known marketplaces and updates each individually
- ✅ **Git Sync**: Snapshots automatically synced to GitHub for multi-machine sharing
- ✅ **Self-sync**: Auto `git pull` on startup to fetch latest snapshot and config
- ✅ **Self-registration**: Prevents Hook loss when plugin operations overwrite `installed_plugins.json`
- ✅ **Global Rules Sync**: Auto-sync `global-rules/CLAUDE.md` to `~/.claude/CLAUDE.md`
- ✅ **Cross-platform Notifications**: System notifications after updates (macOS/Linux/Windows)
- ✅ **Background Execution**: Does not block Claude startup
- ✅ **Log Management**: Auto-rotation, max 10MB retention
- ✅ **One-click Install**: Single script setup on new machines
- ✅ **Cross-platform Support**: macOS, Linux, Windows, DevContainer

## 🚀 Quick Start

### 🤖 Option 1: Claude AI Assistant One-click Setup (Recommended)

**The easiest way**: After launching Claude Code on a new machine, simply tell Claude:

> "Set up my plugins using `git@github.com:hyhmrright/claude-plugins-snapshot.git`"

Claude will automatically:
1. ✅ Clone the repository to `~/.claude/plugins/auto-manager`
2. ✅ Run the install script
3. ✅ Verify the setup
4. ✅ Prompt you to restart Claude Code

**Fully automated, no manual steps required!** 🎉

---

### 🛠️ Option 2: Manual Installation

#### macOS / Linux / DevContainer

```bash
# 1. Clone the repository to Claude plugins directory
cd ~/.claude/plugins/
git clone git@github.com:hyhmrright/claude-plugins-snapshot.git auto-manager

# 2. Run the install script (Python version recommended)
cd auto-manager
python3 install.py

# Or use the Bash script (Unix systems only)
# ./install.sh

# 3. Restart Claude Code
# Plugins will be automatically installed from the snapshot
```

### Windows

```powershell
# 1. Clone the repository to Claude plugins directory
# Note: On Windows, Claude config directory may be at %APPDATA%\Claude
cd %USERPROFILE%\.claude\plugins
git clone git@github.com:hyhmrright/claude-plugins-snapshot.git auto-manager

# 2. Run the Python install script
cd auto-manager
python install.py

# 3. Restart Claude Code
# Plugins will be automatically installed from the snapshot
```

That's it! 🎉

### First-time Setup (Current Machine)

The current machine is already set up, and snapshots are synced to GitHub.

## 📋 How It Works

### Automation Flow

#### SessionStart Hook (On Session Start)

**Every time Claude starts**:
1. **Self-registration Check**: Ensure auto-manager is registered in `installed_plugins.json` (prevents Hook loss)
2. **Self-sync**: `git pull` to fetch latest snapshot and config
3. **Install Missing Plugins**: Compare snapshot with current installation, auto-install missing plugins
   - **Smart Retry**: Auto-retry after 10 minutes on failure, up to 5 attempts
   - **State Tracking**: Track installation status and retry count for each plugin
4. **Global Rules Sync**: Auto-sync `global-rules/CLAUDE.md` to `~/.claude/CLAUDE.md`
5. **Auto Update** (configurable):
   - **Default behavior** (`interval_hours: 0`): Update Marketplaces and all plugins on every startup, ensuring everything is always up-to-date
   - **Scheduled update** (`interval_hours: 24`): Update Marketplaces and plugins every 24 hours
   - **Update order**: Update each Marketplace individually (from `known_marketplaces.json`), then update each plugin
   - **Session detection**: Automatically skip updates when running inside a Claude Code session (avoid nested session errors)
6. **Smart Sync**:
   - ✅ **Plugin list changes** (install/uninstall) → Generate snapshot and push to Git
   - ❌ **Version-only updates** (auto-update) → Don't push, avoid meaningless commits
7. **Log Management**:
   - Auto-rotation, max 10MB retention
   - Keep the most recent 8MB when size is exceeded

### Git Sync Strategy

**Only push to GitHub when**:
- ✅ Plugin list changes detected on startup (install/uninstall)
- ✅ Missing plugins were automatically installed on startup
- ❌ Auto-update (only version number changes, plugin list unchanged)

This avoids generating large numbers of meaningless Git commits daily.

### Syncing After Manual Plugin Install/Uninstall

If you install/uninstall plugins during a session, there are two ways to sync:

1. **Restart Claude Code** (recommended): SessionStart hook will auto-detect and sync
2. **Run sync command manually** (for immediate sync):
   ```bash
   cd ~/.claude/plugins/auto-manager && python3 scripts/sync-snapshot.py
   ```

## 📁 Directory Structure

```
auto-manager/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── hooks/
│   └── hooks.json           # SessionStart Hook configuration
├── scripts/
│   ├── session-start.sh     # Hook entry point (background execution)
│   ├── session-start.py     # Hook entry point fallback (Windows)
│   ├── auto-manager.py      # Main logic (install + update)
│   ├── create-snapshot.py   # Generate plugin snapshot
│   ├── git-sync.py          # Git sync script
│   ├── sync-snapshot.sh     # Manual snapshot sync to Git
│   └── sync-snapshot.py     # Manual snapshot sync (cross-platform)
├── snapshots/
│   ├── current.json         # Current snapshot (single snapshot file)
│   ├── .last-update         # Last update timestamp (local)
│   └── .last-install-state.json  # Install state (local)
├── logs/                    # Runtime logs (local)
│   └── auto-manager.log
├── config.json              # Configuration file
├── install.sh               # New machine install script
├── .gitignore              # Git ignore file
└── README.md               # This document
```

## 🔧 Common Commands

### 📦 Sync Plugins to Git

#### Automatic Sync (Recommended)

The **SessionStart Hook** automatically detects plugin changes and syncs on every Claude Code startup:

1. **After installing/uninstalling plugins**: Restart Claude Code
2. **System auto-detection**: SessionStart hook runs automatically
3. **Smart sync**: Only pushes to GitHub when plugin list has changed

#### Manual Immediate Sync (Optional)

If you don't want to restart, you can manually run the sync command:

```bash
# Recommended (cross-platform)
python3 ~/.claude/plugins/auto-manager/scripts/sync-snapshot.py

# Or use Bash script (Unix systems)
~/.claude/plugins/auto-manager/scripts/sync-snapshot.sh
```

This command will:
1. Generate a new snapshot
2. Detect if there are changes
3. Auto-commit and push to GitHub

#### Verify Sync Results (Optional)

```bash
# View latest commit
cd ~/.claude/plugins/auto-manager && git log -1 --oneline

# Confirm push status
git status -sb

# Check plugin count
cat snapshots/current.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Plugin count: {len(data[\"plugins\"])}')"
```

#### Key Paths

- Plugin directory: `~/.claude/plugins/auto-manager/`
- Git repository: `git@github.com:hyhmrright/claude-plugins-snapshot.git`
- Snapshot file: `~/.claude/plugins/auto-manager/snapshots/current.json`
- Log file: `~/.claude/plugins/auto-manager/logs/auto-manager.log`

### Force Update (Without Waiting 24 Hours)

```bash
python3 ~/.claude/plugins/auto-manager/scripts/auto-manager.py --force-update
```

### View Live Logs

```bash
tail -f ~/.claude/plugins/auto-manager/logs/auto-manager.log
```

### View Snapshot Contents

```bash
cat ~/.claude/plugins/auto-manager/snapshots/current.json
```

## ⚙️ Configuration Options

Edit `config.json` to customize behavior:

```json
{
  "auto_install": {
    "enabled": true              // Enable/disable auto-install
  },
  "auto_update": {
    "enabled": true,             // Enable/disable auto-update
    "interval_hours": 0,         // Update interval (hours)
                                 // 0 = update on every startup
                                 // 24 = update every 24 hours
    "notify": true               // Send system notifications
  },
  "global_sync": {
    "enabled": true              // Sync global-rules/CLAUDE.md to ~/.claude/CLAUDE.md
  },
  "git_sync": {
    "enabled": true,             // Enable Git sync
    "auto_push": true            // Auto-push to remote
  },
  "snapshot": {
    "keep_versions": 10          // Retained snapshot versions (deprecated)
  }
}
```

**Configuration Details**:

- `interval_hours: 0` - **Update on every startup**: Check and update all plugins on every Claude Code startup (recommended)
- `interval_hours: 24` - **Daily update**: Update plugins every 24 hours
- `interval_hours: N` - **Custom interval**: Update every N hours

**Smart Retry Mechanism**:

Automatic retry after plugin installation failure:
- ⏱️ **Retry interval**: 10 minutes
- 🔄 **Max retries**: 5 attempts
- 📊 **State tracking**: Recorded in `snapshots/.last-install-state.json`
- ⚠️ **Limit reached**: Gives up after 5 failures, waits for manual update

**Log Management**:

- 📁 **Log location**: `logs/auto-manager.log`
- 📏 **Size limit**: Max 10MB
- ♻️ **Auto-rotation**: Keeps the most recent 8MB when exceeding 10MB
- 🔒 **Atomic operations**: Uses temporary files to prevent corruption

## 📦 Snapshot File Format

`snapshots/current.json` is the single snapshot file containing all installed plugin information:

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

## 🔄 Multi-Machine Sync Workflow

### Machine A (Install New Plugin)

```bash
# 1. Manually install a new plugin
claude plugin install some-plugin@marketplace

# 2. Sync to GitHub (single command)
python3 ~/.claude/plugins/auto-manager/scripts/sync-snapshot.py
# ✓ Auto-generate snapshot
# ✓ Auto-detect changes
# ✓ Auto-commit and push
```

### Machine B (Auto Sync)

```bash
# Nothing to do!

# On next Claude startup:
# 1. Auto-pull latest snapshot from Git (via git pull)
# 2. Auto-install new plugins
# 3. Auto-update all plugins (if more than 24 hours since last update)
```

**Notes**:
- ✅ Only **plugin list changes** are pushed to Git
- ❌ **Daily auto-updates** are not pushed (avoids meaningless commits)
- 🔄 Other machines will auto-pull and install new plugins

## 🌍 Cross-Platform Support

### Supported Platforms

| Platform | Status | Install Script | Notifications | Notes |
|----------|--------|---------------|---------------|-------|
| macOS | ✅ Fully supported | `install.py` / `install.sh` | osascript | Native support |
| Linux | ✅ Fully supported | `install.py` / `install.sh` | notify-send | Requires desktop environment |
| Windows | ✅ Fully supported | `install.py` | PowerShell Toast | Python script recommended |
| DevContainer | ✅ Fully supported | `install.py` / `install.sh` | May not be available | Notifications optional |
| WSL | ✅ Fully supported | `install.py` / `install.sh` | Depends on environment | Treated as Linux |

### Platform Differences

**Claude Config Directory**:
- macOS/Linux/WSL: `~/.claude`
- Windows: `%APPDATA%\Claude` or `~/.claude`
- DevContainer: `~/.claude` (inside container)

**Notification System**:
- macOS: Uses `osascript` for native notifications
- Linux: Uses `notify-send` (requires libnotify)
- Windows: Uses PowerShell Toast notifications
- DevContainer: May not have desktop environment, notifications auto-skipped

**Install Script Selection**:
- **Recommended**: `python3 install.py` (works on all platforms)
- Alternative: `./install.sh` (Unix systems only, Windows requires Git Bash)

### DevContainer Notes

When using in a DevContainer:

```bash
# 1. Ensure Claude config is mounted in devcontainer.json
{
  "mounts": [
    "source=${localEnv:HOME}/.claude,target=/home/vscode/.claude,type=bind"
  ]
}

# 2. Install inside the container
cd ~/.claude/plugins/
git clone git@github.com:hyhmrright/claude-plugins-snapshot.git auto-manager
cd auto-manager
python3 install.py

# 3. Restart Claude Code (on the host machine)
```

### Windows Notes

**Path Formats**:
```powershell
# PowerShell (recommended)
cd $env:USERPROFILE\.claude\plugins

# CMD
cd %USERPROFILE%\.claude\plugins

# Git Bash
cd ~/.claude/plugins
```

**Execution Permissions**:
Windows does not require `chmod +x`; Python scripts can be run directly.

**SSH Keys**:
Ensure Git SSH keys are configured:
```powershell
# Test GitHub connection
ssh -T git@github.com
```

## ❓ FAQ

### How to disable auto-update?

Edit `config.json` and set `auto_update.enabled` to `false`.

### How to change update frequency?

Edit `config.json` and modify the `auto_update.interval_hours` value (unit: hours).

**Available values**:
- `0` - Update on every Claude Code startup (recommended, ensures plugins are always up-to-date)
- `24` - Update every 24 hours
- Any number - Custom update interval (hours)

**Example**:
```json
{
  "auto_update": {
    "enabled": true,
    "interval_hours": 0,  // Update on every startup
    "notify": true
  }
}
```

### How to view auto-install/update logs?

```bash
tail -f ~/.claude/plugins/auto-manager/logs/auto-manager.log
```

### What to do if Git push fails?

Check:
1. SSH key configured correctly: `ssh -T git@github.com`
2. Remote repository permissions are correct
3. Network connection is working

Even if push fails, local commits will still succeed without affecting plugin management functionality.

### How to use a different snapshot on a new machine?

1. Fork this repository to your own GitHub
2. Modify `snapshots/current.json` to your desired configuration
3. Clone your fork on the new machine:
   ```bash
   git clone git@github.com:your-username/repo-name.git ~/.claude/plugins/auto-manager
   ```

### Why is there only current.json without historical snapshots?

To simplify the Git repository, we only keep the latest snapshot. Git's version history already provides sufficient rollback capability.

### Does the plugin itself auto-update?

No. This is a local plugin (`@local`) and will not be updated via `claude plugin update`.

To update the plugin code:
```bash
cd ~/.claude/plugins/auto-manager
git pull
```

## 🛠️ Troubleshooting

### Plugins Not Auto-Installing

1. Check logs:
   ```bash
   tail ~/.claude/plugins/auto-manager/logs/auto-manager.log
   ```

2. Verify configuration:
   ```bash
   cat ~/.claude/plugins/auto-manager/config.json
   ```

3. Test manually:
   ```bash
   python3 ~/.claude/plugins/auto-manager/scripts/auto-manager.py
   ```

### Updates Not Running

1. Check timestamp:
   ```bash
   cat ~/.claude/plugins/auto-manager/snapshots/.last-update
   ```

2. Force update:
   ```bash
   python3 ~/.claude/plugins/auto-manager/scripts/auto-manager.py --force-update
   ```

### Hook Not Triggering

1. Verify plugin is enabled:
   ```bash
   grep "auto-manager" ~/.claude/settings.json
   ```

2. Check Hook configuration:
   ```bash
   cat ~/.claude/plugins/auto-manager/hooks/hooks.json
   ```

3. Restart Claude Code

## 📚 Related Links

- **Git Repository**: https://github.com/hyhmrright/claude-plugins-snapshot
- **Claude Code Documentation**: https://docs.anthropic.com/claude-code

## 📝 Version History

- **1.1.0** (2026-02-14)
  - Security fixes: session detection, notification escaping, Git whitelist
  - Configuration constants, input validation, type hints
  - Test cases (pytest)
- **1.0.0** (2026-02-07)
  - Initial release
  - Auto-install, auto-update, Git sync support
  - macOS system notifications
  - One-click install script
  - Simplified snapshot management (single current.json)

## 📄 License

MIT License

---

**Need help?** Check the log files or open an Issue on the GitHub repository.
