# ============================================================
# FeFET Approximate CiM — Top-Level Makefile
# IEEE-NANO 2026 Research Project
# ============================================================
#
# Usage:
#   make setup       — Install dependencies and validate environment
#   make validate    — Run smoke tests
#   make baseline    — Run CMOS baseline simulations
#   make approx      — Run CMOS approximate circuit simulations
#   make fefet       — Run FeFET approximate circuit simulations
#   make montecarlo  — Run Monte Carlo variability analysis
#   make benchmark   — Compute metrics and generate comparison tables
#   make images      — Run image processing demo
#   make paper       — Generate all figures and tables for paper
#   make all         — Run full pipeline
#   make clean       — Remove generated files
#
# ============================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Paths ----
PROJECT_ROOT := $(shell pwd)
SCRIPTS := $(PROJECT_ROOT)/scripts
RESULTS := $(PROJECT_ROOT)/results
DOCKER_COMPOSE := docker compose -f docker/docker-compose.yml
DOCKER_RUN := $(DOCKER_COMPOSE) run --rm ngspice
UV_RUN := uv run

# ---- Python Scripts ----
VALIDATE := $(SCRIPTS)/setup/validate_setup.py
COMPILE_OSDI := $(SCRIPTS)/setup/compile_osdi.sh
RUN_SINGLE := $(SCRIPTS)/simulation/run_single.py
RUN_BATCH := $(SCRIPTS)/simulation/run_batch.py
RUN_MC := $(SCRIPTS)/simulation/run_monte_carlo.py
NETLIST_GEN := $(SCRIPTS)/simulation/netlist_generator.py
ERROR_METRICS := $(SCRIPTS)/analysis/compute_error_metrics.py
CIRCUIT_METRICS := $(SCRIPTS)/analysis/compute_circuit_metrics.py
MC_ANALYSIS := $(SCRIPTS)/analysis/monte_carlo_analysis.py
COMP_TABLES := $(SCRIPTS)/analysis/comparison_tables.py
IMAGE_CONV := $(SCRIPTS)/application/image_convolution.py
PLOT_BARS := $(SCRIPTS)/plotting/plot_benchmark_bars.py
PLOT_PARETO := $(SCRIPTS)/plotting/plot_error_pareto.py
PLOT_MC := $(SCRIPTS)/plotting/plot_monte_carlo.py
PLOT_IMAGES := $(SCRIPTS)/plotting/plot_image_comparison.py

# ---- Output Directories ----
RAW_BASELINE := $(RESULTS)/raw/cmos_baseline
RAW_APPROX := $(RESULTS)/raw/cmos_approx
RAW_FEFET := $(RESULTS)/raw/fefet
RAW_MC := $(RESULTS)/raw/monte_carlo
PROCESSED := $(RESULTS)/processed
FIGURES := $(RESULTS)/figures
TABLES := $(PROJECT_ROOT)/paper/tables

# ---- Netlist Paths ----
INVERTER_SP := netlists/cmos_baseline/inverter_cmos45.sp
FA_SP := netlists/cmos_baseline/fa_cmos45.sp

# ============================================================
# Phony targets
# ============================================================
.PHONY: help setup validate compile-osdi \
        baseline approx fefet montecarlo benchmark images \
        truth-tables error-metrics circuit-metrics mc-analysis \
        figures tables paper all clean dirs

# ============================================================
# Help
# ============================================================
help:
	@echo "FeFET Approximate CiM — Research Pipeline"
	@echo ""
	@echo "Targets:"
	@echo "  setup        Install deps and validate environment"
	@echo "  validate     Run environment smoke tests"
	@echo "  baseline     CMOS baseline simulations"
	@echo "  approx       CMOS approximate circuit simulations"
	@echo "  fefet        FeFET approximate circuit simulations"
	@echo "  montecarlo   Monte Carlo variability analysis"
	@echo "  benchmark    Compute metrics and tables"
	@echo "  images       Image processing demo"
	@echo "  paper        Generate all paper figures and tables"
	@echo "  all          Full pipeline"
	@echo "  clean        Remove generated files"

# ============================================================
# Setup
# ============================================================
setup: dirs
	@echo "=== Installing Python dependencies ==="
	uv sync
	@echo ""
	@echo "=== Compiling OSDI models ==="
	-bash $(COMPILE_OSDI)
	@echo ""
	@echo "=== Validating setup ==="
	$(UV_RUN) python $(VALIDATE)

validate:
	$(UV_RUN) python $(VALIDATE)

compile-osdi:
	bash $(COMPILE_OSDI)

dirs:
	@mkdir -p $(RAW_BASELINE) $(RAW_APPROX) $(RAW_FEFET) $(RAW_MC)
	@mkdir -p $(PROCESSED) $(FIGURES) $(TABLES)
	@mkdir -p tests/golden_vectors

# ============================================================
# Simulation Targets
# ============================================================
baseline: dirs
	@echo "=== Running CMOS baseline simulations ==="
	$(DOCKER_RUN) ngspice -b /workspace/$(INVERTER_SP)
	$(DOCKER_RUN) ngspice -b /workspace/$(FA_SP)
	@echo "Baseline simulations complete."

approx: dirs truth-tables
	@echo "=== Running CMOS approximate circuit simulations ==="
	@for circuit in loa heaa ama5; do \
		echo "  Simulating $$circuit..."; \
		$(UV_RUN) python $(RUN_BATCH) \
			--python-only \
			--approx $$circuit \
			--circuit-type adder \
			--n-bits 8 \
			-k 4; \
	done
	@echo "  Simulating BAM multiplier..."
	$(UV_RUN) python $(RUN_BATCH) \
		--python-only \
		--approx bam \
		--circuit-type multiplier \
		--n-bits 4 \
		-k 2
	@echo "Approximate circuit simulations complete."

fefet: dirs compile-osdi
	@echo "=== Running FeFET approximate circuit simulations ==="
	@echo "FeFET simulations require compiled OSDI models and netlist templates."
	@echo "Run individual simulations with:"
	@echo "  $(UV_RUN) python $(RUN_SINGLE) <netlist.sp>"
	@echo ""
	@echo "For batch sweep:"
	@echo "  $(UV_RUN) python $(RUN_BATCH) --template <template.sp> --circuit-type adder"

montecarlo: dirs
	@echo "=== Running Monte Carlo variability analysis ==="
	@echo "Run with:"
	@echo "  $(UV_RUN) python $(RUN_MC) --circuit <netlist> --num-fefets <N> --iterations 1000"

# ============================================================
# Analysis Targets
# ============================================================
truth-tables: dirs
	@echo "=== Generating truth tables ==="
	$(UV_RUN) python $(ERROR_METRICS)

error-metrics: truth-tables
	@echo "=== Computing error metrics ==="
	$(UV_RUN) python $(ERROR_METRICS)

circuit-metrics: dirs
	@echo "=== Computing circuit-level metrics ==="
	$(UV_RUN) python $(CIRCUIT_METRICS)

mc-analysis: dirs
	@echo "=== Processing Monte Carlo results ==="
	$(UV_RUN) python $(MC_ANALYSIS) summary --json-dir $(RAW_MC)

benchmark: error-metrics circuit-metrics
	@echo "=== Benchmark analysis complete ==="

# ============================================================
# Image Processing
# ============================================================
images: dirs
	@echo "=== Running image processing demo ==="
	$(UV_RUN) python $(IMAGE_CONV)

# ============================================================
# Paper Generation
# ============================================================
figures: dirs
	@echo "=== Generating figures ==="
	$(UV_RUN) python $(PLOT_BARS)
	$(UV_RUN) python $(PLOT_PARETO)
	$(UV_RUN) python $(PLOT_MC)
	$(UV_RUN) python $(PLOT_IMAGES)
	@echo "Figures saved to $(FIGURES)/"

tables: dirs
	@echo "=== Generating LaTeX tables ==="
	$(UV_RUN) python $(COMP_TABLES)
	@echo "Tables saved to $(TABLES)/"

paper: figures tables
	@echo "=== Paper assets generated ==="
	@echo "Figures: $(FIGURES)/"
	@echo "Tables:  $(TABLES)/"

# ============================================================
# Full Pipeline
# ============================================================
all: setup baseline approx benchmark images paper
	@echo ""
	@echo "============================================================"
	@echo "Full pipeline complete."
	@echo "  Results:  $(RESULTS)/"
	@echo "  Figures:  $(FIGURES)/"
	@echo "  Tables:   $(TABLES)/"
	@echo "============================================================"

# ============================================================
# Tests
# ============================================================
.PHONY: test
test:
	$(UV_RUN) pytest tests/ -v

# ============================================================
# Clean
# ============================================================
clean:
	@echo "=== Cleaning generated files ==="
	rm -rf $(RESULTS)/raw/batch/
	rm -rf $(RESULTS)/processed/*.csv
	rm -rf $(RESULTS)/figures/*.pdf $(RESULTS)/figures/*.png
	rm -rf $(TABLES)/*.tex
	rm -rf netlists/generated/
	rm -rf netlists/monte_carlo/params/
	rm -f .tmp_*.sp
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete."
