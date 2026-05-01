#!/usr/bin/env bash
#
# Install git pre-commit hooks WITHOUT requiring the pre-commit
# framework (https://pre-commit.com). Reads the canonical
# `.pre-commit-config.yaml` declaration but executes hooks directly
# via the operator's shell environment.
#
# Why this exists alongside `.pre-commit-config.yaml`:
#   - The framework is a pip-installable dependency. Some operators
#     prefer not to add it.
#   - The hooks themselves use `language: system`, so they invoke
#     binaries the operator already has on PATH (`gitleaks`, `python3`).
#   - This script wires up `.git/hooks/pre-commit` to call those
#     binaries directly, mirroring what the framework would do.
#
# If the operator later installs `pre-commit`, running
# `pre-commit install` will overwrite the hook this script creates;
# the same hooks will then run via the framework. The
# `.pre-commit-config.yaml` is the single source of truth either way.
#
# Usage:
#   bash scripts/install-git-hooks.sh
#
# Verify the hook fires on a synthetic test:
#   echo 'FRED_API_KEY=0123456789abcdef0123456789abcdef' > /tmp/leak.md  # gitleaks:allow
#   git add /tmp/leak.md  # this would fail outside repo, just testing
#   git -c hooks.path=.git/hooks commit -m test  # blocks if hook works
#
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_PATH="$REPO_ROOT/.git/hooks/pre-commit"

if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "ERROR: $REPO_ROOT is not a git repository root." >&2
  exit 1
fi

# Verify required binaries are on PATH before installing the hook.
# Better to fail loudly here than silently let commits through later.
missing=()
command -v gitleaks >/dev/null 2>&1 || missing+=("gitleaks")
command -v python3  >/dev/null 2>&1 || missing+=("python3")
if [ ${#missing[@]} -gt 0 ]; then
  echo "ERROR: missing required binaries on PATH: ${missing[*]}" >&2
  echo "Install them, then re-run this script." >&2
  echo "  gitleaks: https://github.com/gitleaks/gitleaks (or 'brew install gitleaks')" >&2
  echo "  python3:  system package or pyenv" >&2
  exit 1
fi

cat > "$HOOK_PATH" <<'HOOK'
#!/usr/bin/env bash
#
# Pre-commit hook installed by scripts/install-git-hooks.sh.
# Reflects the hooks declared in .pre-commit-config.yaml, but
# executes them directly without the pre-commit framework.
#
# To bypass for a specific commit (use sparingly, with reason):
#   git commit --no-verify -m "..."
#
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# 1. Em-dash discipline (text files only, on the staged file list).
STAGED_TEXT_FILES=$(git diff --cached --name-only --diff-filter=ACMR | \
  while read -r f; do
    if [ -f "$f" ] && file "$f" | grep -q "text"; then
      echo "$f"
    fi
  done || true)

if [ -n "$STAGED_TEXT_FILES" ]; then
  # shellcheck disable=SC2086
  python3 scripts/check_no_em_dashes.py $STAGED_TEXT_FILES || {
    echo "" >&2
    echo "[pre-commit] no-em-dashes hook failed. Fix the violations or" >&2
    echo "[pre-commit] (rarely) add to allowlist in scripts/check_no_em_dashes.py." >&2
    exit 1
  }
fi

# 2. gitleaks: scan staged content for secrets.
gitleaks git --staged --config .gitleaks.toml --redact --verbose --no-banner || {
  echo "" >&2
  echo "[pre-commit] gitleaks blocked the commit." >&2
  echo "[pre-commit] If this is a true positive: remove the secret, rotate it," >&2
  echo "[pre-commit] then re-stage and commit. NEVER add secrets to .gitleaksignore." >&2
  echo "[pre-commit] If this is a false positive: extend .gitleaks.toml allowlist" >&2
  echo "[pre-commit] (with reasoning), then re-stage and commit." >&2
  exit 1
}

exit 0
HOOK

chmod +x "$HOOK_PATH"

echo "Installed pre-commit hook at: $HOOK_PATH"
echo "Hooks declared in: .pre-commit-config.yaml"
echo "gitleaks config: .gitleaks.toml"
echo ""
echo "Verify the hook fires:"
echo "  echo 'FRED_API_KEY=0123456789abcdef0123456789abcdef' > _hook_test.md  # gitleaks:allow"
echo "  git add _hook_test.md"
echo "  git commit -m 'test hook' # should be BLOCKED"
echo "  git restore --staged _hook_test.md && rm _hook_test.md"
