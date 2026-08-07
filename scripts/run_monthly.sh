#!/usr/bin/env bash
# Monthly VMRDA plot-watch pipeline.
# Fetches fresh listings, samples ~20/mandal, computes stats, persists the
# monthly snapshot, and regenerates the visualization + blog article.
#
# Safe to run from any directory on any machine with Python 3.9+.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "== VMRDA Plot Watch monthly run: $(date '+%Y-%m-%d %H:%M') =="

python -m pipeline.run --render "$@"

echo "== Done. Snapshot + site + blog updated. =="
