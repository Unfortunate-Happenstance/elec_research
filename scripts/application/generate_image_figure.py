#!/usr/bin/env python3
"""Generate paper-ready image comparison figure + LaTeX Table V.

Reads:  results/figures/<img>_blur_<circuit>.png
        results/processed/image_quality.csv
Writes: results/figures/image_comparison_paper.pdf  (.png)
        paper/tables/table_v_image_quality.tex
"""
from __future__ import annotations
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from skimage import io

ROOT      = Path(__file__).resolve().parent.parent.parent
FIG_DIR   = ROOT / "results" / "figures"
PROC_DIR  = ROOT / "results" / "processed"
TABLE_DIR = ROOT / "paper" / "tables"
TABLE_DIR.mkdir(parents=True, exist_ok=True)

# ── circuits to show (in order) ───────────────────────────────────────────────
CIRCUITS = [
    ("exact",          "Exact"),
    ("loa8_k4",        "LOA-8 (k=4)"),
    ("heaa8_k4",       "HEAA-8 (k=4)"),
    ("ama5_8bit_k4",   "AMA5-8 (k=4)"),
    ("loa8_fefet_var", "LOA-8 FeFET\n(σ=40 mV)"),
]

IMAGES = ["lena", "baboon"]

# ── read CSV ──────────────────────────────────────────────────────────────────
def load_metrics() -> dict:
    """Returns {(image, circuit): (psnr, ssim)}"""
    m = {}
    with open(PROC_DIR / "image_quality.csv") as f:
        for row in csv.DictReader(f):
            m[(row["image"], row["circuit"])] = (
                float(row["blur_psnr_dB"]),
                float(row["blur_ssim"]),
            )
    return m

# ── figure ────────────────────────────────────────────────────────────────────
def make_figure(metrics: dict) -> None:
    n_img  = len(IMAGES)
    n_circ = len(CIRCUITS)

    fig = plt.figure(figsize=(3.5 * n_circ, 3.5 * n_img))
    gs  = gridspec.GridSpec(
        n_img, n_circ,
        figure=fig, hspace=0.05, wspace=0.04,
    )

    for row_i, img_name in enumerate(IMAGES):
        for col_i, (circ_key, circ_label) in enumerate(CIRCUITS):
            ax = fig.add_subplot(gs[row_i, col_i])

            # load image
            img_path = FIG_DIR / f"{img_name}_blur_{circ_key}.png"
            if img_path.exists():
                img = io.imread(str(img_path))
            else:
                img = np.zeros((256, 256), dtype=np.uint8)

            ax.imshow(img, cmap="gray", vmin=0, vmax=255,
                      interpolation="nearest")
            ax.axis("off")

            # column header (top row only)
            if row_i == 0:
                ax.set_title(circ_label, fontsize=9, fontweight="bold", pad=4)

            # row label (leftmost col only)
            if col_i == 0:
                ax.text(-0.08, 0.5, img_name.capitalize(),
                        transform=ax.transAxes,
                        fontsize=9, fontweight="bold",
                        va="center", ha="right", rotation=90)

            # metric annotation (skip for exact — show "Reference")
            key = (img_name, circ_key)
            if circ_key == "exact":
                ann = "Reference"
            elif key in metrics:
                psnr, ssim = metrics[key]
                ann = f"{psnr:.1f} dB\nSSIM {ssim:.3f}"
            else:
                ann = "N/A"

            ax.text(0.97, 0.03, ann,
                    transform=ax.transAxes,
                    fontsize=7.5, color="white",
                    va="bottom", ha="right",
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor="black", alpha=0.55,
                              linewidth=0))

    fig.savefig(str(FIG_DIR / "image_comparison_paper.pdf"),
                bbox_inches="tight", dpi=150)
    fig.savefig(str(FIG_DIR / "image_comparison_paper.png"),
                bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"Figure → {FIG_DIR}/image_comparison_paper.pdf  (.png)")

# ── LaTeX table ───────────────────────────────────────────────────────────────
DISPLAY = {
    "exact":          "Exact (integer)",
    "loa8_k4":        "LOA-8 (k=4)",
    "heaa8_k4":       "HEAA-8 (k=4)",
    "ama5_8bit_k4":   "AMA5-8 (k=4)",
    "loa8_fefet_var": r"LOA-8 FeFET ($\sigma$=40 mV)",
}

def make_latex_table(metrics: dict) -> None:
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Image Quality Results: Gaussian Blur via Approximate Adders}",
        r"\label{tab:image_quality}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"& \multicolumn{2}{c}{\textit{Lena}} & \multicolumn{2}{c}{\textit{Baboon}} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        r"Circuit & PSNR (dB) & SSIM & PSNR (dB) & SSIM \\",
        r"\midrule",
    ]

    for circ_key, disp_name in DISPLAY.items():
        lena_k   = ("lena",   circ_key)
        baboon_k = ("baboon", circ_key)

        if lena_k in metrics:
            lp, ls = metrics[lena_k]
            lena_str = f"{lp:.2f} & {ls:.4f}"
        else:
            lena_str = r"-- & --"

        if baboon_k in metrics:
            bp, bs = metrics[baboon_k]
            baboon_str = f"{bp:.2f} & {bs:.4f}"
        else:
            baboon_str = r"-- & --"

        lines.append(f"{disp_name} & {lena_str} & {baboon_str} \\\\")

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]

    out = TABLE_DIR / "table_v_image_quality.tex"
    out.write_text("\n".join(lines) + "\n")
    print(f"Table  → {out}")

# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    metrics = load_metrics()
    print(f"Loaded {len(metrics)} metric entries from CSV")
    make_figure(metrics)
    make_latex_table(metrics)
    print("Done.")
