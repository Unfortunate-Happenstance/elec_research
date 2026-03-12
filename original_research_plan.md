# Simulation Methodology Research for FeFET CiM Approximate Computing Paper

## Comprehensive findings across all seven research areas

---

## 1. Monte Carlo Simulation in SPICE for FeFET Device Variability

### How Researchers Set Up Monte Carlo Analysis for FeFET

**Compact Model Approach:**
The dominant methodology in 2023-2025 uses **Preisach-based Verilog-A compact models** integrated with industry-standard MOSFET models (BSIM-IMG for FDSOI, BSIM-CMG for FinFET) in commercial SPICE simulators (primarily Cadence Spectre). The FeFET is modeled as a ferroelectric capacitor (Fe-cap) in series with a standard MOSFET, where the Fe-cap captures hysteretic polarization switching and the MOSFET handles transport.

**Key references for compact models:**
- **Temperature- and variability-aware FeFET compact model (2024)** - IIT Kanpur / University of Stuttgart, published in Solid-State Electronics. Preisach-based Verilog-A model in Cadence Spectre. Tested with sigma(V_TH) = 80 mV across -25 to 80C temperature range.
  - Source: https://www.sciencedirect.com/science/article/abs/pii/S0038110124001035
- **HERACLES (2024)** - Open-source HfO2 ferroelectric capacitor compact model (MIT license), Verilog-A, Cadence Spectre. Supports Monte Carlo simulations fitted against statistical device measurements.
  - Source: https://arxiv.org/pdf/2410.07791
- **PFECAP** - Open-source Preisach ferroelectric cap model on GitHub (supadupaplex/pfecap).
  - Source: https://github.com/supadupaplex/pfecap
- **Comprehensive Variability Analysis in Dual-Port FeFET (IEEE TED 2022)** - 34+ citations, foundational variability work. Uses sigma(V_TH) = 40 mV based on theoretical/experimental calibration.
  - Source: https://www.researchgate.net/publication/361925449

### Parameters Varied in Monte Carlo

**Ferroelectric layer parameters:**
1. **Remnant polarization (Pr)** - varies due to non-uniform distribution of ferroelectric grains
2. **Coercive field (Ec)** - varies due to grain-to-grain property differences
3. **Ferroelectric domain distribution** - random spatial distribution of domains with varying size and orientation
4. **Phase composition** - paraelectric/ferroelectric/antiferroelectric phase mixture ratios

**Underlying transistor parameters (same as standard CMOS):**
5. **Work-function variation (WFV)**
6. **Random dopant fluctuations (RDF)**
7. **Line-edge roughness (LER)**

**Combined effect:** Both ferroelectric and transistor sources contribute to V_TH and I_ON variability. Models unify these into an effective V_TH distribution for Monte Carlo.

### Distributions Used

- **Gaussian (normal) distribution** is the standard for V_TH variation in SPICE MC
- In HSPICE syntax: `AGAUSS(mean, sigma, num_sigma)` e.g., `dvtn = AGAUSS(0, 50m, 3)`
- **Caution noted in literature**: Some process parameters do not always follow Gaussian; log-normal may be more appropriate for certain parameters (e.g., leakage current), but Gaussian is the default assumption
- For ferroelectric domain properties, some researchers use **uniform distribution** within physically bounded ranges

### Number of Monte Carlo Iterations

- **1000 iterations** is the most commonly reported count for FeFET CiM variability studies (confirmed in multiple papers)
- **500 iterations** is mentioned as a minimum in the preliminary research document
- **General SPICE MC guidance**: "The higher the number of tests, the better the result, even if this dramatically increases processing time"
- For a conference paper (4-6 pages), **1000 iterations is standard and sufficient**
- For journal papers with extensive statistical analysis, 5000-10000 may be used
- **Recommendation for our paper: 1000 MC iterations** (industry-accepted, computationally feasible, well-justified by literature precedent)

### Practical SPICE Setup

```
* Example MC setup in HSPICE for FeFET variability
.param vth_nom = 0.4
.param vth_sigma = 0.04   $ 40 mV sigma
.param vth_var = AGAUSS(0, 'vth_sigma', 3)

* In the FeFET subcircuit, apply variation:
* V_TH = vth_nom + vth_var

.MC 1000             $ 1000 Monte Carlo iterations
+ PARAM vth_var      $ Parameter to vary
```

---

## 2. FeFET Variability Data (HZO, Cycle-to-Cycle and Device-to-Device)

### Key Paper: Kampfe et al. (2022) - Frontiers in Nanotechnology

**"Random and Systematic Variation in Nanoscale Hf0.5Zr0.5O2 Ferroelectric FinFETs: Physical Origin and Neuromorphic Circuit Implications"**

- Source: https://www.frontiersin.org/journals/nanotechnology/articles/10.3389/fnano.2021.826232/full
- Devices: n-type and p-type tri-gate Fe-FinFETs, L=70nm, W=20nm, H=30nm, T_Fe=10nm
- 2-bit/cell operation demonstrated, 1us write pulse, +-5V, endurance >10^9 cycles
- **D2D variation source**: Paraelectric/ferroelectric phase mixture (incomplete crystallization)
- **C2C variation source**: Random telegraphic noise (trapping/de-trapping events)
- **Key finding**: C2C threshold voltage variation up to 400 mV can be tolerated for MNIST recognition (96.34% accuracy with online training)
- D2D variations reduced to max 10% deviation from mean with surface treatment

### Reported sigma(V_TH) Values from Literature

| sigma(V_TH) | Context | Technology | Year | Source |
|---|---|---|---|---|
| 15 mV | 14nm FinFET baseline (best case) | 14nm CMOS | 2022 | IEEE VLSI |
| 25.69 mV | Dual-bit FeFET lower state | 28nm HKMG | 2025 | npj Unconventional Computing |
| 39.55 mV | Dual-bit FeFET upper state | 28nm HKMG | 2025 | npj Unconventional Computing |
| 40 mV | TCAD-calibrated FeFET model | Generic | 2022 | IEEE TED |
| 80 mV | Temperature-variability compact model | FDSOI | 2024 | Solid-State Electronics |
| 14 mV (3-sigma=42mV) | FeFET TCAM analysis | 28nm | 2023 | Various |

### Variation-Resilient FeFET CiM (Manna et al., 2024, IEEE TED)
- Source: https://arxiv.org/abs/2312.15444
- Derived effective conductance variation model from **experimental C2C and D2D measurements** on 28nm HKMG FeFET
- **Critical finding**: Variations are state-dependent (sigma varies with conductance level), not fixed across all states
- This contradicts earlier models that assumed fixed variation dispersion

### Recommended Values for Our Paper

For a 45nm-equivalent FeFET CiM simulation:
- **D2D sigma(V_TH) = 40-50 mV** (conservative, well-supported by literature)
- **C2C sigma(V_TH) = 20-30 mV** (typical for single-cycle)
- **Pr variation: sigma/mean = 5-10%** (from grain-to-grain variation)
- **Ec variation: sigma/mean = 3-8%** (from grain-to-grain variation)
- Distribution: **Gaussian** for V_TH; can cite Kampfe 2022 for physical justification
- Memory window (MW) typical: 0.5-1.5V for binary states; narrower for MLC

### First Demonstration of In-Memory Computing Crossbar Using Multi-Level Cell FeFET (Nature Communications 2023)
- Source: https://www.nature.com/articles/s41467-023-42110-y
- Experimental FeFET crossbar with MLC operation
- Validates that FeFET variability is a real concern in CiM arrays
- Provides measured data for calibration

---

## 3. CiM Energy/Area/Delay Benchmarking Methodology

### Standard Benchmarking Frameworks

**NeuroSim (Georgia Tech, maintained by Shimeng Yu's group)**
- Source: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2021.659060/full
- C++ based circuit-level macro model for fast design space exploration
- **Inputs**: Memory type (SRAM, RRAM, PCM, FeFET), technology node (130nm-7nm), array size, device parameters
- **Outputs**: Area, latency, dynamic energy, leakage power, inference accuracy
- Validated against 40nm RRAM CiM macro post-layout simulations; chip-level error <1% after calibration
- Latest: **NeuroSim V1.5** (2025) with TensorRT integration, nvCap support, ViT support
  - Source: https://arxiv.org/abs/2505.02314

**Eva-CiM Framework**
- Source: https://dl.acm.org/doi/10.1145/3386263.3407580
- Uniform benchmarking across SRAM, DRAM, FeFET-RAM, STT-MRAM, SOT-MRAM, RRAM
- FeFET-RAM showed ~60% energy savings over CMOS SRAM CiM baseline

**MNSIM 2.0 (TCAD 2023)**
- Behavior-level modeling for processing-in-memory architectures

**AutoDCIM (DAC 2023)**
- Automated digital CIM compiler

### How Energy is Computed

1. **Switching energy (dynamic)**: E_switch = C_load * V_dd^2 * activity_factor
   - For FeFET: includes ferroelectric switching energy (domain rotation) + MOSFET gate charging
   - E_FE_switch proportional to 2 * Pr * A * E_c (polarization reversal energy per unit cell)
2. **Leakage energy**: E_leak = I_leak * V_dd * t_operation
   - FeFET advantage: near-zero standby leakage (non-volatile)
3. **Interconnect energy**: Wire capacitance * V_dd^2 (significant for large arrays)
4. **Peripheral circuit energy**: ADC/DAC, sense amplifiers, row/column drivers
5. **Total energy per MAC operation** = sum of all above components

### How Area is Estimated

**Three approaches commonly used:**
1. **Lambda rules / technology-specific PDK**: For custom layouts. Area = transistor count * min feature pitch
2. **Standard cell library synthesis**: Use Synopsys Design Compiler with foundry PDK (e.g., NanGate 45nm Open Cell Library) for digital peripherals
3. **NeuroSim analytical models**: Pre-calibrated area models per technology node, accounting for transistor sizing, wiring overhead, and layout rules

**For FeFET CiM specifically:**
- Bitcell area: 1FeFET = ~4F^2 to 6F^2 (very compact, comparable to DRAM)
- Array area: bitcell count * bitcell_area + peripheral overhead
- Peripheral area: typically 30-50% of total for analog CiM; 50-70% for digital CiM

### How Delay is Measured

- **Critical path delay** from SPICE transient simulation
- Components: FeFET read/write time + sense amplifier delay + interconnect RC delay + peripheral logic delay
- FeFET write: ~10-100ns (depends on pulse amplitude)
- FeFET read: ~1-10ns (comparable to SRAM)

### Key State-of-the-Art CiM Metrics (2023-2024)

| Design | Technology | Efficiency | Area Efficiency | Source |
|---|---|---|---|---|
| STAR-SRAM (CICC 2024) | 28nm CMOS | 43.06 TFLOPS/W | 1.89 TFLOPS/mm^2 | SRAM digital CiM |
| 22nm ReRAM (ISSCC 2024) | 22nm | 31.2 TFLOPS/W | - | ReRAM CiM |
| FeFET crossbar (Nature Comm 2023) | 28nm | 885.4 TOPS/W | - | 1FeFET-1R MLC |
| 1FeFET-1C (2024) | 28nm | 1000x over GPU | - | Neuro-symbolic AI |

### Recommended Methodology for Our Paper

1. Design approximate arithmetic circuits at transistor/gate level
2. SPICE simulation (HSPICE/ngspice) for energy, delay extraction per operation
3. Area estimation via either:
   - Gate count * standard cell area (from NanGate 45nm library)
   - Custom layout estimation using technology rules
4. Monte Carlo for variability impact on accuracy
5. Compare against CMOS 45nm baseline (same tool flow)
6. Report: Energy/operation (fJ), Area (um^2), Delay (ns), EDP (Energy-Delay Product)

---

## 4. CMOS 45nm Baseline Approximate Circuit Data

### Key Approximate Adder References

**Gupta et al. (2011/2013) - IMPACT Adders**
- "Low-Power Digital Signal Processing Using Approximate Adders"
- IEEE Trans. TCAD, vol. 32, no. 1, pp. 124-137, 2013
- Source: https://ieeexplore.ieee.org/document/6387646/
- Conference version: ISLPED 2011, pp. 409-414
- Proposed imprecise full adder cells with reduced transistor-level complexity
- Demonstrated on DSP architectures (FIR filter, DCT)
- Widely cited (789+ citations) as foundational approximate adder work

**Jiang et al. - Comparative Review of Approximate Adders**
- "A Comparative Review and Evaluation of Approximate Adders" (GLSVLSI 2015)
- Source: http://www.ece.ualberta.ca/~jhan8/publications/AdderComparison4.27.pdf
- Comprehensive comparison of: LOA, ETA (I, II, IV), ACA, COPY, ESA, SCSA, ETAII, ACAA
- Metrics: ER, NMED, MRED, Power, Delay, PDP
- Key findings:
  - LOA: slowest but most power-efficient
  - ACA: most power-consuming with moderate accuracy
  - ESA-3/ESA-4: small PDP but large MRED
  - ETAII-6, LOA-6: small MRED but large PDP

**Key Approximate Adder Designs for Comparison:**

| Adder | Key Property | Typical Power Savings | NMED | ER |
|---|---|---|---|---|
| LOA (Lower-part-OR) | OR gate estimates sum in lower part | High power savings | Medium | ~75% |
| HEAA (Half-precision) | Half-precision estimation | Moderate | Low-medium | ~50% |
| ETA-II (Error Tolerant) | Truncated carry chain, sub-adders | Moderate | Medium | ~50-75% |
| IMPACT/AMA | Reduced transistor FA cells | 25-40% energy savings | Low-medium | Variable |
| COPY (Carry-Output Prediction) | Predicts carry using copy logic | Good tradeoff | Low | Variable |

### Key Approximate Multiplier References

**Jiang et al. - Comparative Evaluation of Approximate Multipliers**
- Source: http://www.ece.ualberta.ca/~jhan8/publications/Multiplier%206.10%20CameraReady.pdf
- Compared: Kulkarni (UDM), BAM, ETM, AWTM, ICM, ACM, TAM1, TAM2, DRUM
- Synthesized with NanGate 45nm Open Cell Library at 0.5-2 GHz
- Key findings (16x16 bit):
  - BAM: very low power, high delay (array structure), large error
  - UDM (Kulkarni): poor PDP-vs-MRED tradeoff, doesn't scale well
  - TAM1, BrnoA2, BrnoA3: best PDP-MRED balance
  - ETM: smallest PDP but large MRED
  - ICM, ACM: very low error but very high PDP

**DRUM (Dynamic Range Unbiased Multiplier)**
- Source: https://ieeexplore.ieee.org/document/7372600/
- Unbiased error distribution (errors cancel out)
- Scalable with parameterizable accuracy
- Verilog source available: https://github.com/scale-lab/DRUM

**Shafique/Rehman - Architectural Space Exploration (ICCAD 2016)**
- Systematic exploration of approximate multiplier design space
- Synthesis with commercial tools and technology libraries

### Specific 45nm Data Points

**From Jiang et al. comparative multiplier study (NanGate 45nm):**
- Accurate 16x16 Wallace multiplier delay: 0.6 ns
- Approximate 16x16 multiplier delay: 0.48 ns (20% reduction)
- Power reduction: up to 69% for aggressive approximation
- One design achieved 66% decrease in PDAP with only 2.5% MRED

**From approximate adder studies:**
- Sobel filter with approximate adders in 45nm: up to 52.7% energy reduction per filtered frame
- ETA designs: 17% power reduction, 29% delay reduction for 4-bit; up to 24% delay reduction for 32-bit

### Error Metrics Definitions

- **NMED** (Normalized Mean Error Distance) = Mean(|exact - approx|) / Max_possible_output
- **MRED** (Mean Relative Error Distance) = Mean(|exact - approx| / exact) [when exact != 0]
- **ER** (Error Rate) = Percentage of erroneous outputs among all outputs
- **PDAP** = Power * Delay * Area Product (combined hardware metric)
- **PDP** = Power * Delay Product

---

## 5. Image Processing Demonstration Methodology

### Standard Approach in Approximate Computing Papers

**Typical demonstration flow:**
1. Implement exact arithmetic kernel (adder/multiplier) in RTL or behavioral model
2. Implement approximate version with same interface
3. Apply both to standard image processing operations
4. Compare output images using quality metrics
5. Report power/energy savings alongside quality degradation

### Common Image Processing Operations Used

1. **Gaussian blur (3x3 or 5x5 kernel)** - Most common; uses additions and multiplications
2. **Sobel edge detection** - Very popular; uses 3x3 convolution with Gx and Gy kernels
3. **Image multiplication/masking** - Direct use of multiplier circuits
4. **Convolution (general NxN)** - Weighted sum using MAC operations
5. **Median filtering** - For denoising
6. **DCT (Discrete Cosine Transform)** - For image compression (JPEG-like)
7. **FIR filtering** - Digital signal processing demonstration

### Standard Test Images

- **Lena** (512x512 grayscale or color) - Most historically used, though declining due to ethical concerns
- **Cameraman** (256x256 grayscale) - MATLAB standard test image
- **Peppers** (512x512 color)
- **Pirate** (512x512)
- **Baboon/Mandrill** (512x512 color) - High texture content
- **Note**: 2017 Journal of Modern Optics editorial suggested Pirate, Cameraman, and Peppers as alternatives to Lena

**Recommendation for our paper**: Use **Cameraman** (grayscale, 256x256) and **Peppers** (color, 512x512) to avoid Lena controversy while maintaining standard practice.

### Typical Methodology from Published Papers

**Rahmani et al. (2023)** - 8x8 approximate multiplier for image processing:
- Applied approximate multiplier in MATLAB for image multiplication
- Measured PSNR improvement of 13-16% and SSIM improvement of ~0.9% vs other approximate designs
- Source: https://link.springer.com/article/10.1007/s00034-023-02418-y

**Approximate adders for Sobel filtering (IEEE 2018)**:
- Sobel precise and approximate architectures in VHDL
- Synthesized for 45nm CMOS
- Mean energy per filtered frame reduction up to 52.7%
- Source: https://ieeexplore.ieee.org/document/8399938

**Approximate 2D convolvers for FPGA (2023)**:
- 3x3 kernel convolution with approximate arithmetic
- 34% power optimization
- Acceptable RMSE and PSNR for real-time applications
- Source: https://link.springer.com/article/10.1007/s11227-023-05377-y

### Expected PSNR Ranges for Approximate Computing

- **Acceptable quality**: PSNR > 25 dB (visible degradation but usable)
- **Good quality**: PSNR > 30 dB (slight degradation, generally acceptable)
- **Excellent quality**: PSNR > 35 dB (minimal visible degradation)
- **Typical range in approximate computing papers**: 25-45 dB depending on approximation level
- SSIM > 0.9 generally considered acceptable; > 0.95 is good

### Recommended Demonstration for Our Paper

1. **Gaussian blur (3x3)** - Primary demonstration
   - 3x3 kernel: [[1,2,1],[2,4,2],[1,2,1]] / 16
   - Each pixel requires 9 multiplications + 8 additions + 1 shift
   - Perfect for showing both approximate adder and multiplier impact

2. **Sobel edge detection** - Secondary demonstration
   - Gx = [[-1,0,1],[-2,0,2],[-1,0,1]]
   - Gy = [[-1,-2,-1],[0,0,0],[1,2,1]]
   - Gradient magnitude = sqrt(Gx^2 + Gy^2) or approx |Gx|+|Gy|

3. **Images**: Cameraman (grayscale) + Peppers (color)
4. **Metrics**: PSNR, SSIM, NMED, visual comparison figures

---

## 6. Python Frameworks for Approximate Computing Quality Evaluation

### Established Libraries

**1. scikit-image (skimage.metrics)**
- `skimage.metrics.peak_signal_noise_ratio(image_true, image_test)`
- `skimage.metrics.structural_similarity(image_true, image_test)`
- `skimage.metrics.mean_squared_error(image_true, image_test)`
- Most widely used in academic papers
- Source: https://scikit-image.org/docs/stable/api/skimage.metrics.html

**2. IQA-PyTorch (pyiqa)**
- PyTorch Toolbox: PSNR, SSIM, LPIPS, FID, NIQE, MUSIQ, TOPIQ, NIMA, DBCNN, BRISQUE
- `pyiqa.create_metric('ssim', device=device)`
- GPU-accelerated for batch processing
- Source: https://github.com/chaofengc/IQA-PyTorch

**3. PIQ (Photosynthesis Image Quality)**
- PyTorch-based, both functional and class interfaces
- Source: https://github.com/photosynthesis-team/piq

**4. Sewar**
- All-in-one: PSNR, SSIM, UQI, MS-SSIM, ERGAS, SCC, RASE, SAM, VIF, PSNR-B
- `pip install sewar`
- Source: https://github.com/andrewekhalel/sewar

**5. Permetrics (for MRE)**
- Performance metrics library including MRE (Mean Relative Error)
- `pip install permetrics`
- Source: https://pypi.org/project/permetrics/

### Custom Implementation Needed for NMED

NMED (Normalized Mean Error Distance) is specific to approximate computing and not in standard image quality libraries. Simple implementation:

```python
import numpy as np

def nmed(exact_output, approx_output, max_possible_value):
    """Normalized Mean Error Distance for approximate computing"""
    return np.mean(np.abs(exact_output.astype(float) - approx_output.astype(float))) / max_possible_value

def mred(exact_output, approx_output):
    """Mean Relative Error Distance"""
    mask = exact_output != 0
    return np.mean(np.abs(exact_output[mask].astype(float) - approx_output[mask].astype(float)) / exact_output[mask].astype(float))

def error_rate(exact_output, approx_output):
    """Percentage of erroneous outputs"""
    return np.mean(exact_output != approx_output) * 100
```

### Recommended Stack for Our Paper

```python
# Core evaluation framework
import numpy as np
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

# For approximate arithmetic simulation
# Option A: Pure Python/NumPy behavioral model
# Option B: Interface with SPICE output files

# Workflow:
# 1. Load test image (Cameraman, Peppers)
# 2. Apply exact convolution kernel
# 3. Apply approximate convolution kernel (using approximate adder/multiplier model)
# 4. Compute: PSNR, SSIM, NMED, MRED, ER
# 5. Generate comparison figures
```

---

## 7. Paper Structure and Scope for 4-6 Page IEEE Conference Paper

### Typical Structure

Based on IEEE Author Center guidelines and published practice:

| Section | Pages | Content |
|---|---|---|
| **Title + Abstract** | 0.25 | Short informative title, 150-200 word abstract |
| **I. Introduction** | 0.75-1.0 | Background, motivation, gap identification, contributions |
| **II. Background / Preliminaries** | 0.5-0.75 | FeFET basics, CiM architecture, approximate computing concepts |
| **III. Proposed Design** | 1.0-1.5 | Circuit architecture, approximate adder/multiplier design, CiM mapping |
| **IV. Simulation Results** | 1.5-2.0 | Monte Carlo results, energy/area/delay comparison, image processing demo |
| **V. Conclusion** | 0.25-0.5 | Summary of contributions, future work |
| **References** | 0.5 | 15-25 references typical for 4-6 page paper |

Source: https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/structure-your-paper/

### Number of Figures

- **4-6 figures** is typical for a 4-6 page paper
- Compress explanations into figures and tables
- **Recommended figure set for our paper:**
  1. FeFET CiM architecture diagram (circuit schematic)
  2. Approximate adder/multiplier circuit design
  3. Monte Carlo V_TH distribution results (histogram)
  4. Energy/Area/Delay comparison bar chart (vs CMOS 45nm baselines)
  5. Image processing quality comparison (visual: exact vs approximate output)
  6. PSNR/SSIM vs energy savings tradeoff curve

### Number of Tables

- **2-3 tables** typical
- Recommended:
  1. Design parameters and simulation setup
  2. Comparison table: Energy, Area, Delay, NMED, MRED vs prior work
  3. Image quality metrics (PSNR, SSIM) across different approximation levels

### Comparison Points Expected by Reviewers

- **3-5 comparison designs minimum**:
  1. Exact CMOS 45nm (baseline)
  2. 1-2 approximate CMOS designs (e.g., LOA adder, DRUM multiplier)
  3. Proposed FeFET CiM approximate design
  4. (Optional) NCFET approximate design if available
- Comparison across **multiple approximation levels** (varying the # of approximate bits)
- Both **hardware metrics** (energy, area, delay) AND **quality metrics** (NMED, PSNR, SSIM)

### Reviewer Expectations

1. **Clear contribution statement** - What is novel? (FeFET + CiM + approximate computing intersection)
2. **Reproducible methodology** - All simulation parameters stated
3. **Fair comparison** - Same technology node, same synthesis flow for baselines
4. **Evidence-backed claims** - Every claim supported by simulation data
5. **Context in prior art** - Differentiate from closest existing work
6. **No plagiarism** - IEEE CrossCheck system enforced
7. **Proper formatting** - IEEE double-column template, 10pt Times Roman

### Formatting

- Double column, single spaced, 10pt Times Roman
- IEEE conference template from IEEE template selector
- LaTeX or Word format
- Source: https://ondezx.com/blog/how-to-write-an-ieee-paper

---

## Summary: Recommended Simulation Methodology for Our Paper

### Complete Workflow

1. **FeFET Compact Model**: Use Preisach-based Verilog-A model (HERACLES or PFECAP, both open-source)
2. **SPICE Simulator**: HSPICE, Cadence Spectre, or ngspice
3. **Approximate Circuit Design**: Lower-part-OR adder + approximate array/tree multiplier mapped to 1FeFET CiM bitcell
4. **Monte Carlo**: 1000 iterations, Gaussian V_TH variation with sigma = 40-50 mV (D2D) and 20-30 mV (C2C)
5. **Baselines**: CMOS 45nm approximate designs (LOA, HEAA, DRUM, BAM) synthesized with NanGate 45nm Open Cell Library
6. **Metrics**: Energy/op (fJ), Area (um^2), Delay (ns), NMED, MRED, ER
7. **Application Demo**: Gaussian blur + Sobel edge detection on Cameraman and Peppers images
8. **Quality Evaluation**: Python (skimage) for PSNR, SSIM; custom code for NMED, MRED
9. **Paper Structure**: 5-6 pages, 5-6 figures, 2-3 tables, 20-25 references

### Key References to Cite

**FeFET Models and Variability:**
- Kampfe et al. (2022), Frontiers in Nanotechnology - D2D and C2C variation sources
- Temperature/variability-aware FeFET compact model (2024), Solid-State Electronics
- HERACLES compact model (2024), arXiv
- Manna et al. (2024), IEEE TED - State-dependent conductance variation
- FeFET CiM crossbar (2023), Nature Communications

**Approximate Computing:**
- Gupta et al. (2013), IEEE TCAD - IMPACT adders
- Jiang et al. (2015), GLSVLSI - Comparative adder review
- Jiang et al. - Comparative multiplier evaluation
- Hashemi/DRUM (2015), ICCAD
- Shafique/Rehman (2016), ICCAD - Multiplier design space

**CiM Benchmarking:**
- NeuroSim (2021/2025), Frontiers in AI / arXiv
- Eva-CiM (2020), GLSVLSI
- FeFET-Based CiM Unit Circuit (2025), PMC

**Image Processing + Approximate Computing:**
- Approximate adders for Sobel (2018), IEEE
- Rahmani et al. (2023), CSSP - 8x8 approximate multiplier for images
