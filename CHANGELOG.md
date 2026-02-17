# Changelog

All notable changes to Claude Plugin Auto-Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Global rules sync: automatically sync `global-rules/CLAUDE.md` to `~/.claude/CLAUDE.md` across machines
- New `global_sync` configuration section in `config.json`
- `global-rules/CLAUDE.md` added to git-sync whitelist
- Windows Hook entry point: `scripts/session-start.py` as alternative for Windows (macOS/Linux continues using `session-start.sh`)
- Per-marketplace updates: read `known_marketplaces.json` and update each marketplace individually with name validation (`_is_valid_marketplace_name()`)
- Self-sync: `git pull --ff-only` on startup to fetch latest snapshot and config before any operations
- Self-registration: auto-register in `installed_plugins.json` on startup to prevent Hook loss from plugin operations rebuilding the file
- SessionStart Hook `matcher: "startup"`: only trigger on new sessions, not on resume/clear/compact (per official Claude Code docs)

### Fixed
- Session detection environment variable: revert v1.1.0 change back to `CLAUDECODE` (confirmed this is the variable actually set by claude CLI; `CLAUDE_CODE_SESSION_ID` was incorrect)
- Self-registration deadlock: call `ensure_self_registered()` after plugin install/update (not just on startup), because `claude plugin install/update` rebuilds `installed_plugins.json` and drops auto-manager registration
- Skip local plugins (without `@marketplace` suffix) in snapshot generation and install, preventing auto-manager from being incorrectly included in `current.json` and causing perpetual install failures
- Race condition: add 10-second startup delay in `session-start.sh` to wait for Claude Code initialization, fixing all plugin updates failing with "not installed" error
- SIGHUP killing background process: use `nohup` + `disown` in `session-start.sh` to ensure background process survives parent shell exit
- Plugin update command format: fallback to base name (without `@marketplace`) when full name returns "not installed" error
- Plugin update retry logic: check both stdout and stderr for "not installed" error (claude CLI may output errors to either stream)
- Plugin update: skip local plugins (without `@marketplace` suffix) in `update_all_plugins()`
- Global hook auto-upgrade: `ensure_global_hook()` now detects and upgrades old hooks missing `matcher` field

## [1.1.0] - 2026-02-14

### Fixed
- 🔴 **Critical**: Fixed session detection environment variable (CLAUDECODE → CLAUDE_CODE_SESSION_ID) *(reverted in later version: CLAUDECODE confirmed correct)*
- 🔴 **Critical**: Fixed retry count logic inconsistency (first failure now sets retry_count=1)
- 🟡 Fixed log rotation seek error when file is smaller than keep_size
- 🟡 Fixed Git add command to only add specific files (prevents accidental commit of sensitive data)
- 🟡 Fixed Windows PowerShell notification script syntax (> $null → | Out-Null)
- 🟢 Fixed timezone inconsistency - all timestamps now use UTC

### Added
- Configuration file version number support (version: "1.0")
- Input validation for plugin name format
- Command injection protection for notification messages
- Constants for all magic numbers (MAX_LOG_SIZE_MB, RETRY_INTERVAL_SECONDS, etc.)
- Unified timeout constants (COMMAND_TIMEOUT_SHORT, COMMAND_TIMEOUT_LONG)
- LICENSE file (MIT License)
- This CHANGELOG file

### Changed
- File permissions changed from 0o755 to 0o744 for better security
- Git sync now only adds specific files instead of all files
- Improved error messages with validation feedback

### Security
- Added escaping for special characters in macOS AppleScript notifications
- Added escaping for special characters in Windows PowerShell notifications
- Reduced file permissions to prevent unauthorized execution

## [1.0.0] - 2026-02-07

### Added
- Initial release
- Auto-install missing plugins from snapshot
- Auto-update plugins with configurable interval
- Smart retry mechanism (10 minutes interval, max 5 retries)
- Git sync with intelligent change detection
- Cross-platform support (macOS, Linux, Windows, DevContainer)
- System notifications for install/update events
- Automatic Claude config backup cleanup
- SessionStart hook integration
- Log rotation (max 10MB)

### Features
- Three-tier architecture (Hook → Manager → Tools)
- Snapshot-based plugin synchronization
- Automatic installation state tracking
- Session detection to avoid nested errors
- Configurable update intervals (0 = every startup, N = hours)
- Smart Git push strategy (only on plugin list changes)

[1.1.0]: https://github.com/hyhmrright/claude-plugins-snapshot/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/hyhmrright/claude-plugins-snapshot/releases/tag/v1.0.0
