#!/usr/bin/env python3
"""Image processing demo with approximate arithmetic.

Applies Gaussian blur and Sobel edge detection using exact vs approximate
adders/multipliers, computing PSNR/SSIM quality metrics.
"""

import numpy as np
from pathlib import Path
from skimage import data, io
from skimage.color import rgb2gray
from skimage.metrics import peak_signal_noise_ratio, structural_similarity
from skimage.util import img_as_ubyte

# Import approximate arithmetic functions
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.analysis.compute_error_metrics import (
    loa_adder, heaa_adder, ama5_adder, bam_multiplier,
)

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"


def load_test_images() -> dict[str, np.ndarray]:
    """Load standard test images as 8-bit grayscale."""
    images = {}

    # Cameraman (256x256) — built into scikit-image
    cam = data.camera()  # Already 8-bit grayscale
    images["cameraman"] = cam

    # Peppers — use coffee image from scikit-image as substitute
    coffee = img_as_ubyte(rgb2gray(data.coffee()))
    images["coffee"] = coffee[:512, :512]  # Crop to square

    return images


def approx_convolve2d(
    image: np.ndarray,
    kernel: np.ndarray,
    adder_func,
    adder_kwargs: dict,
    multiplier_func=None,
    multiplier_kwargs: dict | None = None,
) -> np.ndarray:
    """2D convolution using approximate arithmetic.

    Uses LUT-based approximate add/multiply on 8-bit values.

    Args:
        image: 8-bit grayscale image (H, W)
        kernel: Convolution kernel (kH, kW) with integer weights
        adder_func: Approximate adder function(a, b, n_bits, k)
        adder_kwargs: kwargs for adder (n_bits, k)
        multiplier_func: Optional approximate multiplier
        multiplier_kwargs: kwargs for multiplier

    Returns:
        Filtered image (8-bit)
    """
    h, w = image.shape
    kh, kw = kernel.shape
    pad_h, pad_w = kh // 2, kw // 2
    output = np.zeros_like(image)

    # Precompute exact or approximate multiplication LUT for kernel weights
    # For Gaussian blur kernel [[1,2,1],[2,4,2],[1,2,1]]/16,
    # multiplications are by small constants (1,2,4) — use shift+add
    img = image.astype(np.int64)

    for i in range(pad_h, h - pad_h):
        for j in range(pad_w, w - pad_w):
            acc = np.int64(0)
            for ki in range(kh):
                for kj in range(kw):
                    pixel = img[i - pad_h + ki, j - pad_w + kj]
                    weight = int(kernel[ki, kj])

                    # Multiply pixel by kernel weight
                    if multiplier_func is not None and weight > 0:
                        # Use approximate multiplier
                        prod_arr = multiplier_func(
                            np.array([pixel], dtype=np.int64),
                            np.array([weight], dtype=np.int64),
                            **multiplier_kwargs,
                        )
                        product = int(prod_arr[0])
                    else:
                        product = int(pixel * weight)

                    # Accumulate using approximate adder
                    # Clip to prevent overflow before adding
                    a_val = np.array([int(acc) & 0xFFFF], dtype=np.int64)
                    b_val = np.array([product & 0xFFFF], dtype=np.int64)
                    acc = int(adder_func(a_val, b_val, **adder_kwargs)[0])

            # Normalize (divide by kernel sum)
            kernel_sum = int(np.sum(kernel))
            if kernel_sum > 0:
                acc = acc // kernel_sum

            output[i, j] = np.clip(acc, 0, 255)

    return output.astype(np.uint8)


def gaussian_blur_exact(image: np.ndarray) -> np.ndarray:
    """Gaussian blur (3x3) with exact arithmetic."""
    from scipy.ndimage import convolve
    kernel = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.float64) / 16.0
    return np.clip(convolve(image.astype(np.float64), kernel), 0, 255).astype(np.uint8)


def gaussian_blur_approx(
    image: np.ndarray,
    adder_func,
    adder_n_bits: int = 16,
    adder_k: int = 4,
) -> np.ndarray:
    """Gaussian blur (3x3) using approximate adder for accumulation."""
    kernel = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.int64)
    return approx_convolve2d(
        image, kernel,
        adder_func=adder_func,
        adder_kwargs={"n_bits": adder_n_bits, "k": adder_k},
    )


def sobel_edge_detect_exact(image: np.ndarray) -> np.ndarray:
    """Sobel edge detection with exact arithmetic."""
    from scipy.ndimage import convolve
    gx_kernel = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64)
    gy_kernel = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float64)
    gx = convolve(image.astype(np.float64), gx_kernel)
    gy = convolve(image.astype(np.float64), gy_kernel)
    magnitude = np.sqrt(gx**2 + gy**2)
    return np.clip(magnitude, 0, 255).astype(np.uint8)


def evaluate_image_quality(
    reference: np.ndarray,
    processed: np.ndarray,
) -> dict[str, float]:
    """Compute PSNR and SSIM between reference and processed images."""
    psnr = peak_signal_noise_ratio(reference, processed, data_range=255)
    ssim = structural_similarity(reference, processed, data_range=255)
    return {"PSNR_dB": psnr, "SSIM": ssim}


def run_image_demo():
    """Run full image processing demo."""
    images = load_test_images()
    results = []

    adder_configs = [
        ("exact", None, {}),
        ("LOA_k4", loa_adder, {"adder_n_bits": 16, "adder_k": 4}),
        ("HEAA_k4", heaa_adder, {"adder_n_bits": 16, "adder_k": 4}),
        ("AMA5_k4", ama5_adder, {"adder_n_bits": 16, "adder_k": 4}),
    ]

    for img_name, image in images.items():
        print(f"\n=== {img_name} ({image.shape}) ===")

        # Exact reference
        ref_blur = gaussian_blur_exact(image)
        ref_sobel = sobel_edge_detect_exact(image)

        for adder_name, adder_func, adder_kwargs in adder_configs:
            if adder_func is None:
                # Exact — already computed
                quality_blur = {"PSNR_dB": float("inf"), "SSIM": 1.0}
                quality_sobel = {"PSNR_dB": float("inf"), "SSIM": 1.0}
            else:
                # Approximate blur
                approx_blur = gaussian_blur_approx(
                    image, adder_func, **adder_kwargs
                )
                quality_blur = evaluate_image_quality(ref_blur, approx_blur)

                # Save approximate image
                out_dir = RESULTS_DIR / "figures"
                out_dir.mkdir(parents=True, exist_ok=True)
                io.imsave(
                    str(out_dir / f"{img_name}_blur_{adder_name}.png"),
                    approx_blur,
                )

                # Approximate sobel (placeholder — exact for now)
                quality_sobel = {"PSNR_dB": 0, "SSIM": 0}

            print(f"  {adder_name:10s}  blur: PSNR={quality_blur['PSNR_dB']:6.2f}dB "
                  f"SSIM={quality_blur['SSIM']:.4f}")

            results.append({
                "image": img_name,
                "adder": adder_name,
                "blur_psnr": quality_blur["PSNR_dB"],
                "blur_ssim": quality_blur["SSIM"],
            })

    # Save results
    import pandas as pd
    df = pd.DataFrame(results)
    out_csv = RESULTS_DIR / "processed" / "image_quality.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"\nResults saved to {out_csv}")


if __name__ == "__main__":
    run_image_demo()
