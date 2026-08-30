#!/usr/bin/env bash
# Puts the guard rails on `main`. Run once, straight after the repository goes public —
# rulesets return 403 on a private repository on a free plan, which is why this is a script
# rather than a setting that was always there.
#
# Two rules, in the order #14 argues for:
#
#   1. Nothing may force-push or delete `main`. This one first, and alone if nothing else: a
#      red `main` is a one-minute revert, while overwritten history comes back from somebody's
#      local clone or not at all. It also costs nothing day to day.
#   2. The checks that already run must pass. Named exactly as they report — a required check
#      whose name is wrong never reports, and then nothing can ever merge.
#
# Administrators can bypass, deliberately: a hotfix must never be blocked by the thing that
# was installed to make hotfixes rarer. Requiring a pull request is left out while this is a
# one-person project; it would mean opening a PR to yourself for every commit.
#
# TV Sitter — parental control for Android TV / Google TV.
# Copyright (C) 2026 Tomasz Syc
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail

repo="${1:-TomaszSyc/tvsitter}"

if [ "$(gh api "repos/$repo" --jq .private)" = "true" ]; then
  echo "The repository is still private; rulesets are not available. Nothing done." >&2
  exit 1
fi

gh api --method POST "repos/$repo/rulesets" --input - <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] }
  },
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }
  ],
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          { "context": "Tests and APK" },
          { "context": "Ruff" },
          { "context": "Secret scan" }
        ]
      }
    }
  ]
}
JSON

echo
echo "Ruleset installed. What it does:"
gh api "repos/$repo/rulesets" --jq '.[] | "  \(.name): \(.enforcement)"'
