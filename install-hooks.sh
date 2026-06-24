#!/usr/bin/env bash
set -euo pipefail
if ! git rev-parse --git-dir &>/dev/null; then
    echo "✗  Not a git repository." >&2; exit 1
fi
if ! command -v mnemon &>/dev/null; then
    echo "✗  mnemon not found. Install: uv tool install /path/to/mnemon" >&2; exit 1
fi
HOOK_DIR="$(git rev-parse --git-dir)/hooks"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/git-hooks"
for hook in post-commit post-merge; do
    src="$SCRIPT_DIR/$hook"; dst="$HOOK_DIR/$hook"
    [ -f "$dst" ] && [ ! -L "$dst" ] && mv "$dst" "$dst.bak" && echo "⚠  Backed up $hook"
    ln -sf "$src" "$dst" && chmod +x "$src" && echo "✓  Installed $hook"
done
echo ""
echo "Done. Test: git commit --allow-empty -m 'test: mnemon hook'"
