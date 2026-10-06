#!/usr/bin/env bash
# Install the committed git hooks into .git/hooks/ for this clone.
# Git does NOT version .git/hooks, so re-run this once per fresh clone.
#
#   bash scripts/install-git-hooks.sh
#
# Installs:
#   pre-push -> scripts/commit-guard.sh  (blocks AI/tool attribution + wrong identity)

set -euo pipefail

root="$(git rev-parse --show-toplevel)"
hooks_dir="$root/.git/hooks"
mkdir -p "$hooks_dir"

chmod +x "$root/scripts/commit-guard.sh"

cat > "$hooks_dir/pre-push" <<'EOF'
#!/usr/bin/env bash
# Auto-installed by scripts/install-git-hooks.sh — calls the committed guard.
exec "$(git rev-parse --show-toplevel)/scripts/commit-guard.sh" "$@"
EOF
chmod +x "$hooks_dir/pre-push"

echo "installed: .git/hooks/pre-push -> scripts/commit-guard.sh"
