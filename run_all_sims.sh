#!/usr/bin/env bash
# run_all_sims.sh — re-runs all FeFET MC + sigma sweep simulations
# Usage: bash run_all_sims.sh [WORKERS]   (default: 16)
set -uo pipefail
cd "$(dirname "$0")"

WORKERS="${1:-16}"

ping_error() {
    osascript -e "display notification \"FAILED: $1\" with title \"FeFET Sim\" sound name \"Basso\"" 2>/dev/null || true
    echo "❌  FAILED: $1"
    exit 1
}

step() {
    local label="$1"; shift
    echo ""
    echo "▶  [$label]  $(date '+%H:%M:%S')"
    "$@" || ping_error "$label"
    echo "✓  $label done"
}

# ── Monte Carlo (1000 iters each, overwrites stale results) ──────────────────
# step "MC LOA8"   uv run python scripts/simulation/run_monte_carlo.py \
#     --circuit netlists/monte_carlo/mc_fefet_loa8.sp   --num-fefets 5 \
#     --workers "$WORKERS" --iterations 1000

# step "MC HEAA8"  uv run python scripts/simulation/run_monte_carlo.py \
#     --circuit netlists/monte_carlo/mc_fefet_heaa8.sp  --num-fefets 7 \
#     --workers "$WORKERS" --iterations 1000

# step "MC BAM4x4" uv run python scripts/simulation/run_monte_carlo.py \
#     --circuit netlists/monte_carlo/mc_fefet_bam4x4.sp --num-fefets 4 \
#     --workers "$WORKERS" --iterations 1000

# ── Sigma sweep (200 iters × 5 sigma points, all circuits) ──────────────────
step "Sigma sweep" uv run python scripts/simulation/run_sigma_sweep.py \
    --workers "$WORKERS" --iterations 200 --no-skip

# ── Done ─────────────────────────────────────────────────────────────────────
osascript -e 'display notification "All simulations complete ✓" with title "FeFET Sim" sound name "Glass"' 2>/dev/null || true
echo ""
echo "🎉  All done!"
