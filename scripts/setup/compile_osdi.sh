#!/usr/bin/env bash
# ============================================================
# Compile Verilog-A (.va) files to OSDI (.osdi) inside Docker
#
# Usage:
#   ./scripts/setup/compile_osdi.sh
#
# Requires either:
#   - OpenVAF compiler available in Docker container
#   - Or pre-compiled OSDI files in models/fefet/heracles/
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DOCKER_CONTAINER="ngspice-sim"

HERACLES_VA="models/fefet/heracles/heracles.va"
HERACLES_OSDI="models/fefet/heracles/heracles.osdi"
PFECAP_VA="models/fefet/pfecap/pfecap.va"
PFECAP_OSDI="models/fefet/pfecap/pfecap.osdi"

echo "============================================================"
echo "OSDI Compilation Script"
echo "============================================================"
echo ""

# Check if Docker container is running
docker_available() {
    docker inspect --format='{{.State.Running}}' "$DOCKER_CONTAINER" 2>/dev/null | grep -q "true"
}

# Compile a single .va file to .osdi
compile_va() {
    local va_file="$1"
    local osdi_file="$2"
    local name
    name="$(basename "$va_file" .va)"

    echo "Compiling $va_file -> $osdi_file ..."

    if docker_available; then
        # Try OpenVAF inside Docker
        if docker exec "$DOCKER_CONTAINER" which openvaf >/dev/null 2>&1; then
            echo "  Using OpenVAF in Docker..."
            docker exec -w /workspace "$DOCKER_CONTAINER" \
                openvaf "/workspace/$va_file" \
                --output "/workspace/$osdi_file"

            if [ -f "$PROJECT_ROOT/$osdi_file" ]; then
                echo "  SUCCESS: $osdi_file created"
                return 0
            else
                echo "  WARNING: OpenVAF ran but output not found"
            fi
        else
            echo "  OpenVAF not found in Docker container"
        fi
    else
        echo "  Docker container '$DOCKER_CONTAINER' not running"
    fi

    # Try native OpenVAF
    if command -v openvaf >/dev/null 2>&1; then
        echo "  Using native OpenVAF..."
        openvaf "$PROJECT_ROOT/$va_file" \
            --output "$PROJECT_ROOT/$osdi_file"

        if [ -f "$PROJECT_ROOT/$osdi_file" ]; then
            echo "  SUCCESS: $osdi_file created"
            return 0
        fi
    fi

    # Check for pre-compiled OSDI
    local precompiled_dir
    precompiled_dir="$(dirname "$PROJECT_ROOT/$osdi_file")"

    # Check for platform-specific pre-compiled files
    local platform_osdi=""
    case "$(uname -s)" in
        Linux)  platform_osdi="${precompiled_dir}/${name}_linux_amd64.osdi" ;;
        Darwin) platform_osdi="${precompiled_dir}/${name}_darwin_arm64.osdi" ;;
    esac

    if [ -n "$platform_osdi" ] && [ -f "$platform_osdi" ]; then
        echo "  Using pre-compiled OSDI: $platform_osdi"
        cp "$platform_osdi" "$PROJECT_ROOT/$osdi_file"
        echo "  SUCCESS: Copied pre-compiled OSDI"
        return 0
    fi

    if [ -f "$PROJECT_ROOT/$osdi_file" ]; then
        echo "  Using existing OSDI file (may be outdated)"
        return 0
    fi

    echo "  FAILED: Cannot compile $va_file"
    echo "  Install OpenVAF (https://openvaf.semimod.de/) or provide pre-compiled .osdi"
    return 1
}

# Track results
PASS=0
FAIL=0

# Compile HERACLES
echo ""
if [ -f "$PROJECT_ROOT/$HERACLES_VA" ]; then
    if compile_va "$HERACLES_VA" "$HERACLES_OSDI"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
else
    echo "SKIP: $HERACLES_VA not found"
fi

# Compile PFeCap
echo ""
if [ -f "$PROJECT_ROOT/$PFECAP_VA" ]; then
    if compile_va "$PFECAP_VA" "$PFECAP_OSDI"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
else
    echo "SKIP: $PFECAP_VA not found"
fi

# Summary
echo ""
echo "============================================================"
echo "OSDI Compilation: $PASS succeeded, $FAIL failed"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Note: FeFET simulations require OSDI models."
    echo "If compilation failed, you can:"
    echo "  1. Install OpenVAF: https://openvaf.semimod.de/"
    echo "  2. Place pre-compiled .osdi files in the model directories"
    echo "  3. Run CMOS-only simulations (no OSDI needed)"
    exit 1
fi

exit 0
