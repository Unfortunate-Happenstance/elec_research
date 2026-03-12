#!/usr/bin/env python3
"""Phase 6 — Image processing demo with approximate arithmetic.

Applies 3×3 Gaussian blur using pre-computed 256×256 LUTs derived from
approximate adder truth tables (LOA-8 k=4, HEAA-8 k=4, AMA5-8 k=4).
Also generates a FeFET-variability-perturbed LOA variant.

Algorithm
---------
Kernel: 3×3 Gaussian [[1,2,1],[2,4,2],[1,2,1]], sum = 16.

To avoid 8-bit overflow during accumulation each weighted pixel is
pre-normalised by KERNEL_SUM before adding:

    contrib[dr,dc] = (kernel[dr,dc] * pixel) // 16

Maximum per-term: (4 × 255) // 16 = 63.
Maximum total sum: 4*63 + 4*31 + 4*15 = 252 + 124 + 60 = … wait:
  4 corners (w=1): 4 × 15 = 60
  4 edges   (w=2): 4 × 31 = 124
  1 centre  (w=4): 1 × 63 = 63
  Total max = 247 < 256  ← fits in uint8 throughout, no overflow.

Accumulation uses the approx-adder LUT:
    acc = lut[acc, contrib]   (element-wise numpy fancy indexing)

The final result is the accumulated value (already ≈ the blurred pixel
value on the [0,255] scale; no post-scaling needed).

Images
------
Tries data/images/{lena.png, baboon.png, …} first.
Falls back to skimage.data.camera() (Lena stand-in) and
skimage.data.astronaut() → grayscale (Baboon stand-in).

Output
------
results/figures/<image>_blur_<circuit>.png  — blurred images
results/processed/image_quality.csv         — PSNR / SSIM table
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from skimage import data, io
from skimage.color import rgb2gray
from skimage.metrics import peak_signal_noise_ratio, structural_similarity
from skimage.util import img_as_ubyte

PROJECT_ROOT  = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR    = PROJECT_ROOT / "tests" / "golden_vectors"
FIGURES_DIR   = PROJECT_ROOT / "results" / "figures"
PROCESSED_DIR = PROJECT_ROOT / "results" / "processed"

# ── Gaussian kernel ────────────────────────────────────────────────────────────

KERNEL = np.array([[1, 2, 1],
                   [2, 4, 2],
                   [1, 2, 1]], dtype=np.int32)
KERNEL_SUM = int(KERNEL.sum())   # 16

# List of (row_off, col_off, weight) for the 3×3 kernel
KERNEL_TERMS: list[tuple[int, int, int]] = [
    (r, c, int(KERNEL[r, c]))
    for r in range(3)
    for c in range(3)
]


# ── LUT helpers ────────────────────────────────────────────────────────────────

def load_adder_lut(circuit_name: str) -> np.ndarray:
    """Load 256×256 uint8 approx-adder LUT from truth-table .npz.

    Truth table layout (from compute_error_metrics.py):
        a = np.repeat(np.arange(256), 256)   → index = a_val * 256 + b_val
        b = np.tile(np.arange(256), 256)
    So approx.reshape(256, 256)[a_val, b_val] = approx_sum(a_val, b_val).

    Returns:
        lut: shape (256, 256) uint8, values clipped to [0, 255].
    """
    npz_path = GOLDEN_DIR / f"{circuit_name}_truth_table.npz"
    d = np.load(npz_path)
    approx = d["approx"]                           # shape (65536,), values 0..510
    lut = np.clip(approx, 0, 255).reshape(256, 256).astype(np.uint8)
    return lut


def exact_add_lut() -> np.ndarray:
    """Return 256×256 exact saturating-addition LUT (uint8)."""
    a = np.arange(256, dtype=np.uint16)
    lut = (a[:, None] + a[None, :]).clip(0, 255).astype(np.uint8)
    return lut


def perturb_lut(
    lut: np.ndarray,
    sigma_lsb: float = 5.0,
    seed: int = 42,
) -> np.ndarray:
    """Simulate FeFET VT variability by adding Gaussian noise to the LUT.

    sigma_lsb ≈ 5 LSB corresponds roughly to σ_d2d = 40 mV variability
    (empirically calibrated to match MC NMED ≈ 0.01 at σ_d2d = 40 mV).
    """
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, sigma_lsb, lut.shape).astype(np.float32)
    noisy = np.clip(lut.astype(np.float32) + noise, 0.0, 255.0)
    return noisy.astype(np.uint8)


# ── Image loading ──────────────────────────────────────────────────────────────

def load_test_images() -> dict[str, np.ndarray]:
    """Load Lena and Baboon test images.

    Tries data/images/ first; falls back to scikit-image standard images.
    Returns dict of {name: uint8 grayscale array}.
    """
    img_dir = PROJECT_ROOT / "data" / "images"
    images: dict[str, np.ndarray] = {}

    # ── Lena (or cameraman fallback) ──────────────────────────────────────────
    for fname in ("lena.png", "lena.bmp", "lena_gray.png", "lena512.png",
                  "Lena.png", "Lena512.png"):
        p = img_dir / fname
        if p.exists():
            raw = io.imread(str(p))
            images["lena"] = (
                img_as_ubyte(rgb2gray(raw)) if raw.ndim == 3 else raw
            )[:512, :512]
            print(f"  Loaded lena from {p.name}")
            break
    if "lena" not in images:
        images["lena"] = data.camera()          # 512×512 standard test image
        print("  lena: using skimage.data.camera() fallback")

    # ── Baboon (or astronaut fallback) ────────────────────────────────────────
    for fname in ("baboon.png", "baboon.bmp", "mandrill.png", "Baboon.png"):
        p = img_dir / fname
        if p.exists():
            raw = io.imread(str(p))
            images["baboon"] = (
                img_as_ubyte(rgb2gray(raw)) if raw.ndim == 3 else raw
            )[:512, :512]
            print(f"  Loaded baboon from {p.name}")
            break
    if "baboon" not in images:
        astro = data.astronaut()                # (512, 512, 3) RGB
        images["baboon"] = img_as_ubyte(rgb2gray(astro))[:512, :512]
        print("  baboon: using skimage.data.astronaut() grayscale fallback")

    return images


# ── Gaussian blur ──────────────────────────────────────────────────────────────

def gaussian_blur_exact(image: np.ndarray) -> np.ndarray:
    """Reference Gaussian blur using scipy floating-point arithmetic."""
    from scipy.ndimage import convolve
    k = KERNEL.astype(np.float64) / KERNEL_SUM
    return np.clip(
        convolve(image.astype(np.float64), k), 0.0, 255.0
    ).astype(np.uint8)


def gaussian_blur_lut(image: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Gaussian blur via approximate 8-bit adder LUT (fully vectorised).

    Each weighted pixel contribution is pre-normalised by KERNEL_SUM so
    that all intermediate values remain in [0, 255] (no overflow).

    Uses numpy fancy indexing:
        result[i,j] = lut[acc[i,j], contrib[i,j]]
    which applies the approximate addition table element-wise in O(1).

    Args:
        image: uint8 grayscale array (H, W).
        lut:   (256, 256) uint8 approx adder LUT; lut[a,b] ≈ a+b clipped.

    Returns:
        Blurred image (uint8, same shape as input).
    """
    h, w = image.shape
    # Reflect-pad (1 pixel on each side) for border handling
    padded = np.pad(image, 1, mode="reflect").astype(np.uint8)
    acc = np.zeros((h, w), dtype=np.uint8)

    for dr, dc, kern_weight in KERNEL_TERMS:
        patch = padded[dr: dr + h, dc: dc + w]            # uint8 [0..255]
        # Pre-normalise: contrib = pixel * weight // 16 ∈ [0, 63]
        contrib = (patch.astype(np.uint16) * kern_weight // KERNEL_SUM
                   ).astype(np.uint8)
        # Approximate accumulate: acc ← lut[acc, contrib]
        acc = lut[acc, contrib]

    return acc


# ── Quality metrics ────────────────────────────────────────────────────────────

def compute_quality(
    reference: np.ndarray,
    approx: np.ndarray,
) -> dict[str, float]:
    """Compute PSNR and SSIM vs floating-point reference."""
    psnr = peak_signal_noise_ratio(reference, approx, data_range=255)
    ssim = structural_similarity(reference, approx, data_range=255)
    return {"PSNR_dB": float(psnr), "SSIM": float(ssim)}


# ── Main demo ──────────────────────────────────────────────────────────────────

def run_image_demo() -> None:
    """Run Phase 6 image processing demo end-to-end."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # ── Build LUT dictionary ──────────────────────────────────────────────────
    print("Loading approximate adder LUTs from truth tables …")
    luts: dict[str, np.ndarray] = {
        "exact":          exact_add_lut(),
        "loa8_k4":        load_adder_lut("loa8_k4"),
        "heaa8_k4":       load_adder_lut("heaa8_k4"),
        "ama5_8bit_k4":   load_adder_lut("ama5_8bit_k4"),
        # FeFET-variability-perturbed LOA (σ_d2d ≈ 40 mV → σ ≈ 5 LSB)
        "loa8_fefet_var": perturb_lut(load_adder_lut("loa8_k4"), sigma_lsb=5.0),
    }
    print(f"  LUTs loaded: {list(luts)}")

    # ── Load images ───────────────────────────────────────────────────────────
    print("\nLoading test images …")
    images = load_test_images()
    for name, img in images.items():
        print(f"  {name:12s}  shape={img.shape}  dtype={img.dtype}")

    # ── Run convolutions ──────────────────────────────────────────────────────
    rows: list[dict] = []

    for img_name, image in images.items():
        print(f"\n{'=' * 62}")
        print(f"Image: {img_name}  {image.shape}")
        print(f"{'=' * 62}")

        # Exact float reference (scipy)
        ref = gaussian_blur_exact(image)
        io.imsave(str(FIGURES_DIR / f"{img_name}_blur_exact.png"), ref)

        for lut_name, lut in luts.items():
            blurred = gaussian_blur_lut(image, lut)
            q = compute_quality(ref, blurred)
            psnr, ssim = q["PSNR_dB"], q["SSIM"]

            psnr_str = f"{psnr:7.2f}" if np.isfinite(psnr) else "    inf"
            print(f"  {lut_name:<22s}  PSNR={psnr_str} dB   SSIM={ssim:.5f}")

            io.imsave(
                str(FIGURES_DIR / f"{img_name}_blur_{lut_name}.png"),
                blurred,
            )
            rows.append({
                "image":        img_name,
                "circuit":      lut_name,
                "blur_psnr_dB": round(psnr, 3) if np.isfinite(psnr) else 999.0,
                "blur_ssim":    round(ssim, 5),
            })

    # ── Save CSV ──────────────────────────────────────────────────────────────
    csv_path = PROCESSED_DIR / "image_quality.csv"
    fieldnames = ["image", "circuit", "blur_psnr_dB", "blur_ssim"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults  → {csv_path}")
    print(f"Images   → {FIGURES_DIR}/")


if __name__ == "__main__":
    run_image_demo()
