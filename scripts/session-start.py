#!/usr/bin/env python3
"""
SessionStart Hook entry point (cross-platform).

Launches auto-manager.py in the background with output redirected to log file.
Clears session detection environment variables to allow claude subcommands.
Exits immediately to avoid blocking Claude Code startup.
"""
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path.home() / ".claude" / "plugins" / "auto-manager"))
    log_dir = plugin_root / "logs"
    log_file = log_dir / "auto-manager.log"
    script = plugin_root / "scripts" / "auto-manager.py"

    log_dir.mkdir(parents=True, exist_ok=True)

    # Clear session env vars so the background process can run claude subcommands
    os.environ.pop("CLAUDECODE", None)
    os.environ.pop("CLAUDE_CODE_SESSION_ID", None)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        with open(log_file, "a") as lf:
            lf.write(f"========================================\n[{timestamp}] SessionStart triggered\n")
            lf.flush()

            # Detach child process: setsid on Unix, DETACHED_PROCESS on Windows
            popen_kwargs = {"stdout": lf, "stderr": lf}
            if platform.system() == "Windows":
                popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True

            subprocess.Popen([sys.executable, str(script)], **popen_kwargs)
    except OSError as e:
        print(f"session-start.py: failed to open log file: {e}", file=sys.stderr)
    except Exception as e:
        print(f"session-start.py: failed to launch auto-manager: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
