English | [简体中文](CLAUDE.md)

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code Plugin Auto-Manager that implements automatic plugin installation, updates, and cross-machine synchronization through SessionStart Hook. It is a local plugin (`@local`) deployed at `~/.claude/plugins/auto-manager/`.

**Current Version**: v1.1.0 (2026-02-14) - Includes important security fixes and code quality improvements

## Core Architecture

### Three-Layer Automation Architecture

1. **Hook Layer** (`hooks/hooks.json`)
   - SessionStart Hook triggers on every Claude Code startup
   - Calls `scripts/session-start.sh` for background execution (avoids blocking startup)
   - `scripts/session-start.py` provides Windows alternative entry point (configure in `install.py`)
   - Timeout setting: 30 seconds

2. **Management Layer** (`scripts/auto-manager.py`)
   - **Main logic**: Coordinates install, update, and sync functionality
   - **Smart retry**: Auto-retry 10 minutes after installation failure, up to 5 attempts, state recorded in `.last-install-state.json`
   - **Session detection**: Auto-detects if running inside a Claude Code session (checks `CLAUDECODE` environment variable) to avoid nested session errors
   - **Self-sync**: Auto `git pull` on startup to fetch latest snapshot and config
   - **Self-registration**: Ensures itself is registered in `installed_plugins.json` on startup and after each plugin install/update, preventing Hook loss from Claude Code rebuilding the file
   - **Per-marketplace updates**: Reads `known_marketplaces.json` and updates each marketplace individually (with name validation)
   - **Scheduled updates**: Based on `interval_hours` configuration in `config.json` (0=every startup, 24=daily update)
   - **Log management**: Auto-rotation, truncates to 8MB when exceeding 10MB
   - **Backup cleanup**: Auto-deletes Claude Code generated `~/.claude.json.backup.<timestamp>` backup files on each startup, keeping only the main backup file
   - **Global rules sync**: Automatically syncs global rules from the repository to `~/.claude/CLAUDE.md`
   - **Configuration constants**: All magic numbers extracted as named constants (v1.1.0)

3. **Tool Layer**
   - `create-snapshot.py`: Generates snapshots from Claude configuration files (with input validation)
   - `git-sync.py`: Syncs snapshots to Git repository (only adds specific files)
   - `sync-snapshot.py`: Manually triggers snapshot sync (cross-platform)

### Key Constants (Added in v1.1.0)

All configuration constants are defined at the top of `scripts/auto-manager.py`:

```python
# Config paths
KNOWN_MARKETPLACES_FILE = CLAUDE_DIR / "plugins" / "known_marketplaces.json"

# Log management
MAX_LOG_SIZE_MB = 10           # Maximum log size
KEEP_LOG_SIZE_MB = 8           # Size to keep after rotation

# Retry mechanism
RETRY_INTERVAL_SECONDS = 600   # Retry interval (10 minutes)
MAX_RETRY_COUNT = 5            # Maximum retry count

# Timeout (seconds)
COMMAND_TIMEOUT_SHORT = 60     # Git operations, snapshot creation
COMMAND_TIMEOUT_LONG = 120     # Plugin install/update
```

**Note when modifying constants**: References in code and test cases must be updated simultaneously

### Key Data Files

```
snapshots/
├── current.json              # Single snapshot file (Git-tracked)
├── .last-update              # Last update timestamp (local, Git-ignored)
└── .last-install-state.json  # Install retry state (local, Git-ignored)

global-rules/
└── CLAUDE.md                 # Global rules file (Git-tracked, synced to ~/.claude/CLAUDE.md)

logs/
└── auto-manager.log          # Runtime log (local, Git-ignored)
```

### Smart Git Sync Strategy

**Only pushes to GitHub when**:
- ✅ Plugin list changes detected on startup (plugins added/removed)
- ✅ Missing plugins were automatically installed on startup
- ❌ Version-only updates (auto-updating plugin versions) do not push

**Implementation**:
- Compares plugin key sets between current and newly generated snapshots (`set(plugins.keys())`)
- Same → Skip push (only version numbers changed)
- Different → Generate snapshot and push (plugin list changed)

## Common Commands

### Development and Testing

```bash
# Manually run the manager (test install and update logic)
python3 scripts/auto-manager.py

# Force update all plugins (ignore time interval)
python3 scripts/auto-manager.py --force-update

# Manually generate snapshot
python3 scripts/create-snapshot.py

# Manually sync snapshot to Git (recommended, cross-platform)
python3 scripts/sync-snapshot.py

# Or use Bash script (Unix systems only)
./scripts/sync-snapshot.sh

# View live logs
tail -f logs/auto-manager.log

# View current snapshot
cat snapshots/current.json | python3 -m json.tool

# View install retry state
cat snapshots/.last-install-state.json | python3 -m json.tool
```

### Running Tests (Added in v1.1.0)

```bash
# Install dependencies (managed with uv)
uv sync

# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_auto_manager.py -v

# View code coverage
uv run pytest tests/ --cov=scripts --cov-report=html
# Then open htmlcov/index.html to view the report

# Run specific test class only
uv run pytest tests/test_auto_manager.py::TestRetryLogic -v
```

### Deploy to New Machine

```bash
# 1. Clone repository to Claude plugins directory
cd ~/.claude/plugins/
git clone git@github.com:hyhmrright/claude-plugins-snapshot.git auto-manager

# 2. Run install script (cross-platform)
cd auto-manager
python3 install.py

# 3. Restart Claude Code
# SessionStart Hook will automatically install all plugins from the snapshot
```

### Git Operations

```bash
# View Git status (in auto-manager directory)
git status

# View latest commit
git log -1 --oneline

# Manually pull latest snapshot
git pull

# View plugin count
cat snapshots/current.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Plugin count: {len(data[\"plugins\"])}')"
```

## Configuration File Reference

### `config.json` Structure

```json
{
  "version": "1.0",          // Added in v1.1.0: config file version
  "auto_install": {
    "enabled": true          // Enable/disable auto-install of missing plugins
  },
  "auto_update": {
    "enabled": true,         // Enable/disable auto-update
    "interval_hours": 0,     // Update interval (hours)
                             // 0 = update on every startup
                             // 24 = update every 24 hours
    "notify": true           // Send system notifications (macOS/Linux/Windows)
  },
  "global_sync": {
    "enabled": true          // Sync global-rules/CLAUDE.md to ~/.claude/CLAUDE.md
  },
  "git_sync": {
    "enabled": true,         // Enable Git sync
    "auto_push": true        // Auto-push to remote
  },
  "snapshot": {
    "keep_versions": 10      // Legacy field, currently unused
  }
}
```

### `snapshots/current.json` Structure

```json
{
  "version": "1.0",
  "timestamp": "2026-02-14T03:00:13Z",
  "plugins": {
    "plugin-name@marketplace": {
      "enabled": true,
      "version": "commit-sha-or-version",
      "marketplace": "marketplace-name",
      "gitCommitSha": "full-commit-sha"  // Optional
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

## How It Works

### SessionStart Hook Execution Flow

1. **Trigger**: On every Claude Code startup
2. **Backup cleanup**: Auto-deletes timestamped config backup files generated by Claude Code
   - Deletes files matching `~/.claude.json.backup.<timestamp>` pattern
   - Preserves `~/.claude.json.backup` (main backup file)
   - Purpose: Prevent unlimited accumulation of backup files consuming disk space
3. **Self-registration check**: Ensures auto-manager is registered in `installed_plugins.json`
   - Prevents loss when Claude Code plugin operations rebuild the file
   - Missing registration causes Hook to stop triggering
4. **Self-sync**: `git pull --ff-only` to fetch latest snapshot and config
   - Runs before `load_config()` to ensure latest remote config is used
   - Not controlled by `git_sync.enabled` (read-only operation, config not yet loaded)
5. **Session detection**: Checks `CLAUDECODE` environment variable
   - If inside a Claude Code session → Skip updates (avoid nested session errors)
   - If not in a session → Execute normally
   - `session-start.py` unsets this variable before launching the background process
6. **Install missing plugins**:
   - Read plugin list from `snapshots/current.json`
   - Compare with installed list in `~/.claude/plugins/installed_plugins.json`
   - Install missing plugins
   - Record failures to `.last-install-state.json` for later retry
   - **Re-register self after install** (`claude plugin install` rebuilds `installed_plugins.json`)
7. **Global rules sync**:
   - Read `global-rules/CLAUDE.md`
   - Compare with `~/.claude/CLAUDE.md` contents
   - Changed → Update target file
   - Unchanged → Skip
8. **Smart retry**:
   - Read failure records from `.last-install-state.json`
   - Check if 10-minute retry interval has elapsed
   - Retry count under 5 → Retry installation
   - Over 5 → Temporarily give up, wait for manual intervention
9. **Scheduled update** (configurable):
   - Check `.last-update` timestamp
   - If time since last update exceeds `interval_hours` → Execute update
   - `interval_hours: 0` → Update on every startup
10. **Update flow**:
    - First update each Marketplace individually (`claude plugin marketplace update <name>`)
    - Reads all marketplaces from `~/.claude/plugins/known_marketplaces.json`
    - Then update each installed plugin individually (`claude plugin update <name>`)
    - **Re-register self after update** (`claude plugin update` rebuilds `installed_plugins.json`)
11. **Git sync**:
    - Generate new snapshot
    - Compare if plugin list has changed
    - Changed → Commit and push
    - Unchanged → Skip (only version numbers updated)
12. **System notifications** (configurable):
    - macOS: Uses `osascript`
    - Linux: Uses `notify-send`
    - Windows: Uses PowerShell Toast

### Retry Mechanism Details

**State file format** (`.last-install-state.json`):
```json
{
  "plugin-name@marketplace": {
    "last_attempt": "2026-02-14T03:00:13Z",
    "retry_count": 2,
    "error": "Installation failed: timeout"
  }
}
```

**Retry logic** (fixed in v1.1.0):
- Check all failed plugins on each startup
- Calculate time since last attempt
- **First failure**: `retry_count = 1` (v1.1.0 fix: was incorrectly set to 0 before)
- If `now - last_attempt >= RETRY_INTERVAL_SECONDS` and `retry_count <= MAX_RETRY_COUNT`:
  - Retry installation
  - Success → Remove from state file
  - Failure → Increment `retry_count`
- If `retry_count > MAX_RETRY_COUNT` → Skip, log warning

## Cross-Platform Support

### Supported Platforms

| Platform | Status | Claude Config Directory | Install Script | Notification System |
|----------|--------|------------------------|---------------|-------------------|
| macOS | ✅ | `~/.claude` | `install.py` / `install.sh` | `osascript` |
| Linux | ✅ | `~/.claude` | `install.py` / `install.sh` | `notify-send` |
| Windows | ✅ | `%APPDATA%\Claude` or `~/.claude` | `install.py` | PowerShell Toast |
| WSL | ✅ | `~/.claude` | `install.py` / `install.sh` | Depends on environment |
| DevContainer | ✅ | `~/.claude` | `install.py` / `install.sh` | May not be available |

### Platform-Specific Notes

**Windows**:
- Recommended to use `install.py` (works with PowerShell or CMD)
- Use paths like `%USERPROFILE%\.claude\plugins` or `$env:USERPROFILE\.claude\plugins`
- No `chmod +x` needed, Python scripts can run directly

**DevContainer**:
- Need to mount Claude config directory in `devcontainer.json`
- System notifications may not be available (no desktop environment)

**macOS/Linux**:
- Prefer `install.py` (better cross-platform compatibility)
- `install.sh` as fallback (pure Bash)

## Log Management

**Log rotation strategy**:
- Maximum size: 10MB
- Keep after rotation: 8MB (most recent logs)
- Implementation: Atomic operations (using temporary files)
- Failure handling: Log rotation failure does not affect main flow

**Log format**:
```
[2026-02-14T03:00:13Z] Log message
```

## Troubleshooting

### Plugins Not Auto-Installing

1. Check logs: `tail -f logs/auto-manager.log`
2. Check configuration: `cat config.json`
3. Check if plugin is enabled: `grep "auto-manager" ~/.claude/settings.json`
4. Test manually: `python3 scripts/auto-manager.py`
5. Check retry state: `cat snapshots/.last-install-state.json`

### Updates Not Running

1. Check timestamp: `cat snapshots/.last-update`
2. Check configuration: `cat config.json | grep interval_hours`
3. Force update: `python3 scripts/auto-manager.py --force-update`
4. Check session environment: `echo $CLAUDECODE` (should be empty)

### Git Push Failure

1. Check SSH: `ssh -T git@github.com`
2. Check remote repository: `git remote -v`
3. Manual push: `cd snapshots && git push`
4. Check permissions: Ensure write access to the repository

### Hook Not Triggering

1. Check plugin enabled state: `cat ~/.claude/settings.json | grep enabledPlugins`
2. Check Hook configuration: `cat hooks/hooks.json`
3. Restart Claude Code
4. View startup logs: `tail -f logs/auto-manager.log`

## Code Modification Guidelines

### When Modifying Python Scripts

1. **Maintain cross-platform compatibility**: Use `Path` instead of string paths, avoid hardcoded path separators
2. **Maintain backward compatibility**: Provide default values when modifying config format
3. **Error handling**: Important operation failures should not interrupt the entire flow (e.g., log rotation failure)
4. **Atomic operations**: Use temporary files when modifying config files to prevent corruption
5. **Use constants**: Don't hardcode magic numbers, use constants defined at file top (v1.1.0)
6. **Type hints**: Add complete type hints for new functions `typing.Dict[str, Any]` etc. (v1.1.0)
7. **Docstrings**: Include parameter and return value descriptions (v1.1.0)
8. **Input validation**: Validate all external input (plugin name format, config values, etc.) (v1.1.0)
9. **Security**:
   - Escape all strings passed to shell (prevent command injection)
   - Use UTC timestamps (avoid timezone issues)
   - Git operations only add specific files, never use `git add .`

### When Modifying Hook Configuration

1. **Avoid blocking**: SessionStart Hook must execute in background (`&`)
2. **Timeout settings**: Hook timeout should be long enough (currently 30 seconds) but not too long
3. **Log redirection**: All output redirected to `logs/auto-manager.log`

### When Modifying Snapshot Format

1. **Maintain version number**: `version: "1.0"` for future compatibility checks
2. **Backward compatibility**: New fields should be optional (with default values)
3. **Git-friendly**: Maintain consistent JSON formatting (2-space indentation)

### When Adding New Features

1. **Write tests**: Add corresponding test cases in the `tests/` directory (v1.1.0)
2. **Update documentation**: Update both CLAUDE.md and README.md
3. **Update CHANGELOG**: Record in the Unreleased section of CHANGELOG.md
4. **Code review**: Run `pytest tests/ -v` to ensure all tests pass

### Important Security Fixes (v1.1.0)

1. **Session detection environment variable**: Must use `CLAUDECODE` (confirmed as the variable actually used by claude CLI; v1.1.0 incorrectly changed to `CLAUDE_CODE_SESSION_ID`, corrected in later version)
2. **Notification message escaping**:
   - macOS: `escape_for_applescript()` - Escapes `\` and `"`
   - Windows: `escape_for_powershell()` - Escapes `"` and `$`
3. **Git security**: Only add whitelisted files, prevent sensitive data leaks
4. **File permissions**: Script permissions use `0o744` (not `0o755`)

## Git Repository Information

- **Repository URL**: `git@github.com:hyhmrright/claude-plugins-snapshot.git`
- **Local path**: `~/.claude/plugins/auto-manager/`
- **Tracked files**:
  - Config: `config.json`, `.gitignore`
  - Docs: `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `LICENSE`
  - Code: `scripts/`, `hooks/`, `install.py`, `install.sh`
  - Snapshot: `snapshots/current.json`
  - Tests: `tests/` (added in v1.1.0)
- **Ignored files**: `logs/`, `snapshots/.last-update`, `snapshots/.last-install-state.json`
- **Git sync strategy** (v1.1.0 security enhancement):
  - Whitelist mode: Only add specific files to Git
  - Prevent sensitive data leaks (.env, credentials, private keys, etc.)

## Multi-Machine Sync Workflow

### Machine A (Install New Plugin)
1. Manual install: `claude plugin install plugin-name@marketplace`
2. Sync snapshot: `python3 ~/.claude/plugins/auto-manager/scripts/sync-snapshot.py`
   - Auto-generate snapshot
   - Detect plugin list changes
   - Commit and push to GitHub

### Machine B (Auto Sync)
1. On next Claude Code startup:
   - SessionStart Hook triggers automatically
   - Pull latest snapshot from Git (if auto_pull is enabled)
   - Detect and install missing plugins
   - Update plugins based on configuration
