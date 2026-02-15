---
name: sync
description: Sync plugin snapshot to Git. Use when user wants to sync plugins, push snapshot, or after installing/removing plugins.
user_invocable: true
---

# Sync Plugin Snapshot

Run the sync-snapshot script to generate a snapshot and push to Git:

```bash
python3 ~/.claude/plugins/auto-manager/scripts/sync-snapshot.py
```

After running, report the result to the user:
- If successful: confirm the plugin count and that changes were pushed
- If no changes: inform the user the snapshot is already up to date
- If push failed: note that changes are committed locally and suggest checking SSH/remote config
