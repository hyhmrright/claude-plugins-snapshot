# Changelog

All notable changes to Claude Plugin Auto-Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-14

### Fixed
- 🔴 **Critical**: Fixed session detection environment variable (CLAUDECODE → CLAUDE_CODE_SESSION_ID)
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
