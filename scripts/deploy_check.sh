#!/usr/bin/env bash
# Deploy discipline gate. Print the cost frame for the next
# fly deploy so the operator sees what a deploy actually costs
# in compute and ram before triggering it. Soft gate, not a
# hard block. The point is felt friction, not enforcement.
#
# Usage:
#   scripts/deploy_check.sh
#   scripts/deploy_check.sh && fly deploy --build-arg GIT_SHA=$(git rev-parse --short HEAD)
#
# Pricing assumptions (shared-cpu-1x:512MB on Fly.io as of 2026-05):
#   CPU portion always-on:  $1.94/mo
#   RAM 512MB always-on:    $2.50/mo  ($5/GB-mo)
#   Total awake rate:       $4.44/mo = $0.00617/hour = $0.000103/min
#   Autosuspend grace:      ~7 min after last activity (verified
#                           in production logs 2026-05-03)
#
# When Fly raises rates or the machine size changes, update the
# RATE_USD_PER_HOUR constant below; the rest is derived.

set -euo pipefail

APP="${APP:-fabrication-profiler}"
RATE_USD_PER_HOUR="0.00617"
GRACE_MIN="7"

if ! command -v fly >/dev/null 2>&1; then
  echo "fly CLI not found on PATH; skipping deploy check." >&2
  exit 0
fi

releases_json=$(fly releases -a "$APP" --json 2>/dev/null || echo "[]")
machines_json=$(fly machine list -a "$APP" --json 2>/dev/null || echo "[]")

# Python parses the JSON, computes intervals, prints the frame.
# Embedded as heredoc rather than separate file so this script
# is self-contained and works from a fresh checkout without a
# scripts/__init__.py shuffle.
python3 - "$APP" "$RATE_USD_PER_HOUR" "$GRACE_MIN" <<'PY' "$releases_json" "$machines_json"
import json
import sys
from datetime import datetime, timezone

app, rate_str, grace_str = sys.argv[1], sys.argv[2], sys.argv[3]
releases_raw, machines_raw = sys.argv[4], sys.argv[5]
rate_per_hour = float(rate_str)
grace_min = int(grace_str)

try:
    releases = json.loads(releases_raw) if releases_raw.strip() else []
except json.JSONDecodeError:
    releases = []
try:
    machines = json.loads(machines_raw) if machines_raw.strip() else []
except json.JSONDecodeError:
    machines = []

now = datetime.now(timezone.utc)

def parse_iso(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None

last_release_at = None
if releases:
    last_release_at = parse_iso(releases[0].get("CreatedAt"))

deploys_last_1h = sum(
    1 for r in releases
    if (t := parse_iso(r.get("CreatedAt"))) and (now - t).total_seconds() < 3600
)
deploys_last_24h = sum(
    1 for r in releases
    if (t := parse_iso(r.get("CreatedAt"))) and (now - t).total_seconds() < 86400
)

machine_state = machines[0].get("state", "unknown") if machines else "no-machine"
machine_updated_at = parse_iso(machines[0].get("updated_at")) if machines else None

print("─" * 60)
print(f"Deploy discipline check  ({app})")
print("─" * 60)

if last_release_at is None:
    print("Last release:        (none)")
else:
    delta = now - last_release_at
    mins = int(delta.total_seconds() // 60)
    if mins < 60:
        print(f"Last release:        {mins} min ago")
    else:
        print(f"Last release:        {mins // 60}h {mins % 60}m ago")

print(f"Machine state:       {machine_state}")
print(f"Deploys in last 1h:  {deploys_last_1h}")
print(f"Deploys in last 24h: {deploys_last_24h}")

# Cost frame
hourly = rate_per_hour
print()
print(
    f"Cost frame (shared-cpu-1x:512MB, ${hourly:.4f}/h awake, "
    f"~{grace_min}-min autosuspend grace):"
)
print(
    f"  - Each isolated deploy: ~${hourly * grace_min / 60:.4f} "
    "(one wake + grace cycle)"
)
print(
    f"  - Back-to-back deploys keep the machine awake continuously."
)
print(
    f"  - 18 deploys in 14h (May 2 pattern) ≈ "
    f"${hourly * 14:.2f} of avoidable awake time that day."
)

# Friction signals
flags = []
if last_release_at is not None and (now - last_release_at).total_seconds() < grace_min * 60:
    flags.append(
        f"⚠ Last deploy was within the {grace_min}-min autosuspend window. "
        "Machine is still awake from it; this deploy extends the awake "
        "window rather than starting a new one."
    )
if deploys_last_1h >= 3:
    flags.append(
        f"⚠ {deploys_last_1h} deploys in the last hour. "
        "If you are using fly deploy as a feedback loop, switch to local "
        "uvicorn on :8001."
    )
if deploys_last_24h >= 10:
    flags.append(
        f"⚠ {deploys_last_24h} deploys in the last 24h. "
        "Heavy churn day. Worth a pause to ask: is the next deploy a "
        "feature ship, a hotfix, or another tweak-and-see?"
    )

if flags:
    print()
    for f in flags:
        print(f)

print()
print("Deploy when one of these is true:")
print("  [ ] Feature complete and reviewable")
print("  [ ] Hotfix verified locally first")
print("  [ ] Production-only verification needed (Litestream / R2 / edge)")
print("  [ ] End-of-session batched ship")
print()
print("Default loop is local: uvicorn at :8001 covers most cases.")
print("─" * 60)
PY

# Soft prompt. Skip if not running interactively (CI, scripts).
if [ -t 0 ] && [ -t 1 ]; then
  read -r -p "Press Enter to proceed with deploy, or Ctrl-C to cancel. "
fi
