#!/usr/bin/env python3
"""IEEE-compatible matplotlib configuration for publication-quality figures.

Provides consistent styling across all plots:
  - Fonts: Times New Roman / serif, 8pt labels, 7pt ticks
  - Figure sizes: 1-column (3.5in), 2-column (7.16in)
  - Colorblind-friendly palette
  - Line and marker style cycles
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"

# ---- Color Palette (colorblind-friendly) ----
# Based on Paul Tol's palette and common accessibility recommendations
COLORS = {
    "blue": "#0077BB",
    "orange": "#EE7733",
    "green": "#009988",
    "red": "#CC3311",
    "purple": "#AA3377",
    "cyan": "#33BBEE",
    "gray": "#BBBBBB",
    "black": "#000000",
}

COLOR_CYCLE = [
    COLORS["blue"],
    COLORS["orange"],
    COLORS["green"],
    COLORS["red"],
    COLORS["purple"],
    COLORS["cyan"],
]

# ---- Line and Marker Styles ----
LINE_STYLES = ["-", "--", "-.", ":", "-", "--"]
MARKER_STYLES = ["o", "s", "^", "D", "v", "P"]
MARKER_SIZE = 4

# ---- Figure Dimensions (inches) ----
FIG_WIDTH_1COL = 3.5       # IEEE single column
FIG_WIDTH_2COL = 7.16      # IEEE double column
FIG_HEIGHT_DEFAULT = 2.5    # Default height for single plots
FIG_HEIGHT_TALL = 4.5       # For multi-subplot figures
ASPECT_RATIO = 0.7          # height/width for default figures

# ---- Font Sizes (pt) ----
FONT_SIZE_LABEL = 8
FONT_SIZE_TICK = 7
FONT_SIZE_TITLE = 9
FONT_SIZE_LEGEND = 7
FONT_SIZE_ANNOTATION = 6


def apply_ieee_style():
    """Apply IEEE-compatible matplotlib style settings.

    Call this function before creating any figures to ensure
    consistent publication-quality styling.
    """
    plt.style.use("default")  # Reset to defaults first

    mpl.rcParams.update({
        # Font family
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",  # STIX fonts match Times well

        # Font sizes
        "font.size": FONT_SIZE_LABEL,
        "axes.labelsize": FONT_SIZE_LABEL,
        "axes.titlesize": FONT_SIZE_TITLE,
        "xtick.labelsize": FONT_SIZE_TICK,
        "ytick.labelsize": FONT_SIZE_TICK,
        "legend.fontsize": FONT_SIZE_LEGEND,

        # Figure
        "figure.figsize": (FIG_WIDTH_1COL, FIG_WIDTH_1COL * ASPECT_RATIO),
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,

        # Axes
        "axes.linewidth": 0.5,
        "axes.prop_cycle": mpl.cycler(color=COLOR_CYCLE),
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,

        # Ticks
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.minor.width": 0.3,
        "ytick.minor.width": 0.3,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.minor.size": 1.5,
        "ytick.minor.size": 1.5,
        "xtick.direction": "in",
        "ytick.direction": "in",

        # Lines
        "lines.linewidth": 1.0,
        "lines.markersize": MARKER_SIZE,

        # Legend
        "legend.frameon": True,
        "legend.framealpha": 0.9,
        "legend.edgecolor": "0.8",
        "legend.fancybox": False,
        "legend.handlelength": 1.5,
        "legend.labelspacing": 0.3,
        "legend.columnspacing": 1.0,

        # Grid
        "grid.linewidth": 0.3,
        "grid.alpha": 0.5,

        # PDF/PS output
        "pdf.fonttype": 42,  # TrueType fonts in PDF (required by IEEE)
        "ps.fonttype": 42,
    })


def get_figure_1col(
    n_rows: int = 1,
    n_cols: int = 1,
    height_per_row: float | None = None,
    **kwargs,
) -> tuple[plt.Figure, plt.Axes | np.ndarray]:
    """Create a single-column figure with IEEE dimensions.

    Args:
        n_rows: Number of subplot rows
        n_cols: Number of subplot columns
        height_per_row: Height per row in inches (auto-computed if None)
        **kwargs: Additional kwargs passed to plt.subplots()

    Returns:
        (fig, axes) tuple
    """
    import numpy as np

    if height_per_row is None:
        height_per_row = FIG_WIDTH_1COL * ASPECT_RATIO

    fig_height = height_per_row * n_rows
    fig, axes = plt.subplots(
        n_rows, n_cols,
        figsize=(FIG_WIDTH_1COL, fig_height),
        **kwargs,
    )
    return fig, axes


def get_figure_2col(
    n_rows: int = 1,
    n_cols: int = 1,
    height_per_row: float | None = None,
    **kwargs,
) -> tuple[plt.Figure, plt.Axes | np.ndarray]:
    """Create a double-column figure with IEEE dimensions.

    Args:
        n_rows: Number of subplot rows
        n_cols: Number of subplot columns
        height_per_row: Height per row in inches (auto-computed if None)
        **kwargs: Additional kwargs passed to plt.subplots()

    Returns:
        (fig, axes) tuple
    """
    import numpy as np

    if height_per_row is None:
        height_per_row = FIG_WIDTH_2COL * ASPECT_RATIO / 2

    fig_height = height_per_row * n_rows
    fig, axes = plt.subplots(
        n_rows, n_cols,
        figsize=(FIG_WIDTH_2COL, fig_height),
        **kwargs,
    )
    return fig, axes


def save_figure(
    fig: plt.Figure,
    name: str,
    output_dir: Path | None = None,
    formats: list[str] | None = None,
):
    """Save figure in publication formats.

    Args:
        fig: Matplotlib figure to save
        name: Base filename (without extension)
        output_dir: Directory to save to (defaults to results/figures/)
        formats: List of formats to save (defaults to ['pdf', 'png'])
    """
    if output_dir is None:
        output_dir = FIGURES_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if formats is None:
        formats = ["pdf", "png"]

    for fmt in formats:
        filepath = output_dir / f"{name}.{fmt}"
        fig.savefig(filepath, format=fmt, bbox_inches="tight", pad_inches=0.02)
        print(f"  Saved: {filepath}")


def annotate_subplot(ax: plt.Axes, label: str, x: float = -0.15, y: float = 1.05):
    """Add subplot label (a), (b), etc. in IEEE style.

    Args:
        ax: Axes to annotate
        label: Label text, e.g., '(a)'
        x: Relative x position
        y: Relative y position
    """
    ax.text(
        x, y, label,
        transform=ax.transAxes,
        fontsize=FONT_SIZE_LABEL,
        fontweight="bold",
        va="bottom",
        ha="right",
    )


# Technology markers for scatter plots
TECH_MARKERS = {
    "CMOS": {"marker": "o", "color": COLORS["blue"], "label": "CMOS"},
    "FeFET": {"marker": "s", "color": COLORS["orange"], "label": "FeFET"},
    "NCFET": {"marker": "^", "color": COLORS["green"], "label": "NCFET"},
}


if __name__ == "__main__":
    # Demo: show the style configuration
    apply_ieee_style()

    fig, (ax1, ax2) = get_figure_1col(n_rows=1, n_cols=2)

    import numpy as np
    x = np.linspace(0, 2 * np.pi, 100)
    for i, (ls, ms) in enumerate(zip(LINE_STYLES[:4], MARKER_STYLES[:4])):
        ax1.plot(
            x, np.sin(x + i * 0.5),
            linestyle=ls, marker=ms, markevery=15,
            label=f"Signal {i+1}",
        )
    ax1.set_xlabel("Time (ns)")
    ax1.set_ylabel("Voltage (V)")
    ax1.legend()
    annotate_subplot(ax1, "(a)")

    bars = ax2.bar(
        ["Exact", "LOA", "HEAA", "AMA5"],
        [0, 0.035, 0.022, 0.048],
        color=COLOR_CYCLE[:4],
        edgecolor="black",
        linewidth=0.5,
    )
    ax2.set_ylabel("NMED")
    annotate_subplot(ax2, "(b)")

    fig.tight_layout()
    save_figure(fig, "style_demo")
    plt.close(fig)
    print("Style demo saved.")
