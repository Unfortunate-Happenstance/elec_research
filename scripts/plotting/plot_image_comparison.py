#!/usr/bin/env python3
"""Image comparison grid for approximate arithmetic visual quality demo.

Layout: 2-row grid showing:
  Row 1: Original, LOA blur, HEAA blur, AMA5 blur
  Row 2: Corresponding PSNR/SSIM annotations (overlaid or as text)

Uses cameraman test image from scikit-image.
Reads processed images from results/figures/.
Saves to results/figures/image_comparison.pdf.
"""

import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"

import sys
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.plotting.style import (
    apply_ieee_style,
    save_figure,
    COLORS,
    FONT_SIZE_LABEL,
    FONT_SIZE_ANNOTATION,
    FONT_SIZE_TICK,
    FIG_WIDTH_2COL,
)


# Image configurations
IMAGE_CONFIGS = [
    {"name": "Original", "suffix": None, "psnr": float("inf"), "ssim": 1.0},
    {"name": "LOA (k=4)", "suffix": "LOA_k4", "psnr": None, "ssim": None},
    {"name": "HEAA (k=4)", "suffix": "HEAA_k4", "psnr": None, "ssim": None},
    {"name": "AMA5 (k=4)", "suffix": "AMA5_k4", "psnr": None, "ssim": None},
]


def load_quality_metrics(csv_path: Path | None = None) -> dict:
    """Load image quality metrics from CSV.

    Args:
        csv_path: Path to image_quality.csv

    Returns:
        Dict mapping (image_name, adder_name) -> {PSNR, SSIM}
    """
    if csv_path is None:
        csv_path = PROCESSED_DIR / "image_quality.csv"

    if not csv_path.exists():
        return {}

    import pandas as pd
    df = pd.read_csv(csv_path)
    metrics = {}
    for _, row in df.iterrows():
        key = (row.get("image", ""), row.get("adder", ""))
        metrics[key] = {
            "PSNR": row.get("blur_psnr", None),
            "SSIM": row.get("blur_ssim", None),
        }
    return metrics


def load_images(
    image_name: str = "cameraman",
) -> dict[str, np.ndarray]:
    """Load original and processed images.

    First tries loading from saved files. Falls back to generating
    on-the-fly using the image convolution script.

    Args:
        image_name: Base name of the test image

    Returns:
        Dict mapping config name -> image array
    """
    images = {}

    # Try loading original from scikit-image
    try:
        from skimage import data
        if image_name == "cameraman":
            images["Original"] = data.camera()
        else:
            images["Original"] = data.camera()
    except ImportError:
        # Create a simple test pattern
        x = np.linspace(0, 4 * np.pi, 256)
        xx, yy = np.meshgrid(x, x)
        images["Original"] = ((np.sin(xx) * np.sin(yy) + 1) * 127.5).astype(np.uint8)

    # Try loading processed images from files
    for config in IMAGE_CONFIGS[1:]:  # Skip "Original"
        suffix = config["suffix"]
        img_path = FIGURES_DIR / f"{image_name}_blur_{suffix}.png"

        if img_path.exists():
            from skimage import io
            img = io.imread(str(img_path))
            if img.ndim == 3:
                from skimage.color import rgb2gray
                from skimage.util import img_as_ubyte
                img = img_as_ubyte(rgb2gray(img))
            images[config["name"]] = img
        else:
            images[config["name"]] = None

    return images


def plot_image_comparison(
    image_name: str = "cameraman",
    quality_csv: Path | None = None,
    output_name: str = "image_comparison",
):
    """Generate image comparison grid figure.

    Args:
        image_name: Base name of test image
        quality_csv: Path to image_quality.csv with PSNR/SSIM
        output_name: Base filename for output
    """
    apply_ieee_style()

    images = load_images(image_name)
    quality = load_quality_metrics(quality_csv)

    # Determine number of columns (only images that exist)
    valid_configs = []
    for config in IMAGE_CONFIGS:
        if config["name"] in images and images[config["name"]] is not None:
            valid_configs.append(config)

    if not valid_configs:
        print("No images found. Creating placeholder figure.")
        valid_configs = IMAGE_CONFIGS[:4]

    n_cols = len(valid_configs)

    # Create figure: 2 rows (images + metrics bar)
    fig_height = FIG_WIDTH_2COL / n_cols * 1.3  # Aspect ratio with annotation
    fig, axes = plt.subplots(
        2, n_cols,
        figsize=(FIG_WIDTH_2COL, fig_height),
        gridspec_kw={"height_ratios": [5, 1]},
    )

    if n_cols == 1:
        axes = axes.reshape(2, 1)

    for col_idx, config in enumerate(valid_configs):
        ax_img = axes[0, col_idx]
        ax_text = axes[1, col_idx]

        name = config["name"]
        suffix = config["suffix"]

        # Display image
        img = images.get(name)
        if img is not None:
            ax_img.imshow(img, cmap="gray", vmin=0, vmax=255)
        else:
            # Placeholder
            ax_img.text(
                0.5, 0.5, "Not\navailable",
                transform=ax_img.transAxes,
                ha="center", va="center",
                fontsize=FONT_SIZE_LABEL,
            )

        ax_img.set_title(name, fontsize=FONT_SIZE_LABEL, pad=3)
        ax_img.axis("off")

        # Quality metrics annotation
        ax_text.axis("off")

        if suffix is None:
            # Original — show "Reference"
            ax_text.text(
                0.5, 0.5, "Reference",
                transform=ax_text.transAxes,
                ha="center", va="center",
                fontsize=FONT_SIZE_TICK,
                style="italic",
            )
        else:
            # Look up quality metrics
            psnr_val = None
            ssim_val = None

            # Try from CSV
            key = (image_name, suffix)
            if key in quality:
                psnr_val = quality[key].get("PSNR")
                ssim_val = quality[key].get("SSIM")

            # Try from config
            if psnr_val is None:
                psnr_val = config.get("psnr")
            if ssim_val is None:
                ssim_val = config.get("ssim")

            # Format text
            lines = []
            if psnr_val is not None and not np.isinf(psnr_val):
                lines.append(f"PSNR: {psnr_val:.1f} dB")
            if ssim_val is not None:
                lines.append(f"SSIM: {ssim_val:.4f}")

            if lines:
                text = "\n".join(lines)
                ax_text.text(
                    0.5, 0.5, text,
                    transform=ax_text.transAxes,
                    ha="center", va="center",
                    fontsize=FONT_SIZE_TICK,
                    family="monospace",
                    bbox=dict(
                        boxstyle="round,pad=0.3",
                        facecolor="lightyellow",
                        edgecolor="gray",
                        linewidth=0.5,
                    ),
                )
            else:
                ax_text.text(
                    0.5, 0.5, "N/A",
                    transform=ax_text.transAxes,
                    ha="center", va="center",
                    fontsize=FONT_SIZE_TICK,
                    style="italic",
                )

    fig.tight_layout(h_pad=0.5, w_pad=0.5)
    save_figure(fig, output_name)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot image comparison grid"
    )
    parser.add_argument("--image", type=str, default="cameraman",
                        help="Test image name")
    parser.add_argument("--quality-csv", type=str, default=None,
                        help="Path to image_quality.csv")
    parser.add_argument("--output", type=str, default="image_comparison")
    args = parser.parse_args()

    quality = Path(args.quality_csv) if args.quality_csv else None
    plot_image_comparison(args.image, quality, output_name=args.output)
