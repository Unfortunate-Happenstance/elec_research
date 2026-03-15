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
# LOA-8: 200 iterations, 5 FeFETs
# uv run python scripts/simulation/run_monte_carlo.py \
#   --circuit netlists/monte_carlo/mc_fefet_loa8.sp \
#   --num-fefets 5 --iterations 200 --workers 12 --seed 42

# # HEAA-8: 50 iterations, 7 FeFETs
# uv run python scripts/simulation/run_monte_carlo.py \
#   --circuit netlists/monte_carlo/mc_fefet_heaa8.sp \
#   --num-fefets 7 --iterations 50 --workers 12 --seed 42

# # BAM 4x4: 200 iterations, 4 FeFETs
# uv run python scripts/simulation/run_monte_carlo.py \
#   --circuit netlists/monte_carlo/mc_fefet_bam4x4.sp \
#   --num-fefets 4 --iterations 200 --workers 12 --seed 42


# ── Sigma sweep (200 iters × 5 sigma points, all circuits) ──────────────────
step "Sigma sweep" uv run python scripts/simulation/run_sigma_sweep.py \
    --workers "$WORKERS" --iterations 50 --no-skip

# ── Done ─────────────────────────────────────────────────────────────────────
osascript -e 'display notification "All simulations complete ✓" with title "FeFET Sim" sound name "Glass"' 2>/dev/null || true
echo ""
echo "🎉  All done!"
