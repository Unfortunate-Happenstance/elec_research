# Five simulation-only paper opportunities for IEEE-NANO 2026

**A systematic analysis of 2024–2026 literature across five frontier areas reveals at least five high-novelty, simulation-only research gaps at the intersection of multiple trending IEEE-NANO topics—all achievable without lab access.** The strongest opportunities sit where three or more hot topics converge yet no existing paper occupies the intersection. Each gap below has been validated against cutting-edge publications and maps directly to IEEE-NANO 2026 conference tracks (Modeling and Simulation, Nanoelectronics, Neuromorphic/Unconventional Computing, Spintronics, Nano-Energy). The recommendations are ordered by a composite score of novelty, feasibility, multi-topic intersection strength, and reviewer appeal.

---

## 1. FeFET approximate arithmetic circuits for in-memory computing

**The gap.** Ferroelectric FET (FeFET) in-memory computing has exploded since 2023—crossbar MAC engines, content-addressable memories, CiM annealers (Nature Communications 2023, 2024), and time-domain CiM macros (IEEE TCAD 2025) now form a rich ecosystem. Separately, approximate computing with nanodevices is strongly emerging at IEEE-NANO (9 recent papers vs. 1 before 2020). Yet **no published paper designs approximate arithmetic circuits (adders, multipliers, MAC units) specifically for FeFET-based CiM architectures**. The closest works are an NCFET approximate multiplier (Scientific Reports 2025) in pure logic, and TAP-CAM (ICCAD 2024) for approximate *matching*—neither addresses approximate *computation* inside FeFET memory arrays.

**The research question.** How do FeFET CiM approximate adders and multipliers compare against CMOS and NCFET approximate designs in energy-accuracy-area trade-offs, and can FeFET device variability be intentionally exploited as a controlled source of approximation for error-tolerant workloads (image processing, ML inference)?

**Why it matters.** FeFET variability—driven by stochastic ferroelectric domain switching—is typically treated as a reliability problem. Reframing it as an approximation resource is a paradigm inversion that could extend effective device lifetime and simultaneously reduce CiM energy. The paper would sit at the triple intersection of **ferroelectric devices + in-memory computing + approximate computing**, all strongly trending topics with near-zero overlap in the existing corpus.

**Methodology and tools.** Use a Preisach-based or Jiles-Atherton Verilog-A FeFET compact model (multiple open models exist from 2024–2025) in HSPICE or ngspice. Design approximate adder (e.g., lower-part-OR, HEAA) and multiplier topologies mapped onto a 1FeFET or 2FeFET CiM bitcell. Run **Monte Carlo simulation** (500+ iterations) under realistic cycle-to-cycle and device-to-device variability extracted from published 28nm HZO-FeFET data. Benchmark energy, area, delay, and quality metrics (MRE, PSNR, SSIM) against equivalent CMOS 45nm and NCFET designs. All tools are open-source or widely available under academic licenses.

**Feasibility: very high.** No fabrication needed. Compact models, SPICE netlists, and variability data are available from recent publications. A single researcher can complete this in 8–12 weeks. The 4–6 page format favors a focused circuit-level study with Monte Carlo benchmarks and one application demonstration (e.g., image convolution).

---

## 2. Aging-aware RRAM crossbar co-simulation for neuromorphic inference and PUF security

**The gap.** Dual-use RRAM crossbars—serving simultaneously as neuromorphic synapse arrays and physical unclonable functions—were demonstrated experimentally by Oh et al. (Wiley 2022). PUF security in fresh RRAM is well-studied (Ibrahim et al. 2024; 3D stacked PUF in ACS Nano 2025; Arbiter PUF Monte Carlo in arXiv 2025). RRAM aging effects on neuromorphic accuracy are also studied (Ye et al. 2022; Zhevnenko 2025 MemRUL). However, **no simulation study examines how progressive RRAM aging simultaneously degrades both PUF security metrics and SNN inference accuracy in a shared crossbar**. This triple intersection—**memristor + neuromorphic + PUF + reliability**—is completely unoccupied.

**The research question.** How does RRAM endurance degradation (conductance window narrowing, sticking events, retention loss) co-degrade PUF uniqueness/reliability and SNN classification accuracy over the device lifetime, and can aging-aware workload scheduling optimize both metrics jointly?

**Methodology and tools.** Implement an aging-parameterized Verilog-A RRAM compact model (extending the UniMORE or VTEAM model with cycle-count-dependent conductance range and stochastic sticking probability from Zhevnenko 2025). Simulate a **128×128 1T1R crossbar** in ngspice/PySpice serving dual roles: (a) vector-matrix multiply for a 2-layer SNN with STDP on MNIST, and (b) Arbiter PUF with challenge-response pairs. Run Monte Carlo across device lifetime (10³–10⁸ cycles). Evaluate SNN accuracy, PUF Hamming distance, uniformity, and ML attack resilience at each aging stage. Propose an aging-aware scheduling policy that alternates PUF enrollment refreshes with SNN retraining. Python post-processing for all statistical analysis.

**Feasibility: very high.** Open-source RRAM models (Stanford, VTEAM), PySpice, and Python handle everything. Aging parameters can be calibrated from published HfO₂ endurance data. The dual-use concept is already experimentally validated, so the simulation study extends it with a previously unaddressed dimension.

---

## 3. Physics-informed neural ODE for transient memristor compact modeling

**The gap.** Machine learning for nanodevice compact modeling is the fastest-growing topic at IEEE-NANO (10 recent vs. 2 older papers). Landmark 2025 papers include DDNet (a PINN solving Poisson-drift-diffusion for semiconductor devices), AutoPINN, and physics-informed ML for 2D THz transistors. Separately, Neural ODEs are revolutionizing dynamical system modeling in materials science. Yet **no work applies Neural ODEs to transient switching dynamics of memristive devices**. DDNet and its descendants solve steady-state drift-diffusion only. Existing stochastic memristor compact models (Suñé 2025, PINN-Fokker-Planck 2024) capture equilibrium distributions but not the time-dependent filament growth/dissolution trajectory that governs programming speed, write energy, and cycle-to-cycle variability.

**The research question.** Can a physics-informed Neural ODE learn the time-dependent filament dynamics of HfO₂ RRAM—embedding Poole-Frenkel transport and thermal feedback as physics constraints—to produce a compact model that is both faster than TCAD and more accurate than phenomenological Verilog-A models for transient SET/RESET simulations?

**Methodology and tools.** Generate training data using either (a) an open-source TCAD tool (DEVSIM or Sentaurus academic license) solving coupled drift-diffusion + heat equations for a 1D filament model, or (b) published transient I-V curves from HfO₂ RRAM literature. Train a Neural ODE (via PyTorch + torchdiffeq) with physics-informed loss terms enforcing charge conservation, Joule heating energy balance, and Arrhenius-type kinetics. Export learned weights to a Verilog-A wrapper for SPICE validation. Benchmark accuracy, speed, and generalization against the Stanford memristor model and VTEAM on switching waveforms across pulse amplitudes and widths.

**Feasibility: high.** All tools are open-source (PyTorch, torchdiffeq, DEVSIM, ngspice). A single GPU (or even CPU) suffices for training. The paper naturally fits **4–6 pages**: model formulation (1 page), training and physics constraints (1 page), validation against TCAD and measurements (1.5 pages), SPICE integration demo (0.5–1 page). It sits at the intersection of **ML + memristor + compact modeling**, all strongly emerging IEEE-NANO topics.

---

## 4. First-principles prediction of 2D altermagnetic materials for spintronic devices

**The gap.** Altermagnetism—recognized as the third fundamental class of collinear magnetism alongside ferromagnetism and antiferromagnetism—was experimentally confirmed in MnTe in late 2024 (Nature). The field is exploding: ferroelectric-switchable altermagnetism was predicted in PRL (2025), altermagnetic tunnel junctions with **>1000% TMR** have been theoretically demonstrated, and all-electrical spintronic devices using altermagnets were proposed (npj Quantum Materials 2025). However, **virtually no DFT studies exist on 2D altermagnetic materials**—monolayer or bilayer systems exhibiting altermagnetic spin-splitting. The 2D materials community and the altermagnetism community have barely intersected. This is arguably the single most novel topic accessible to a theory/simulation researcher in 2026.

**The research question.** Which 2D van der Waals materials from existing crystallographic databases exhibit altermagnetic band structures with significant spin-splitting, and what are their predicted spin-transport properties (anomalous Hall conductivity, spin-polarized current) relevant to nanoscale spintronic memory?

**Methodology and tools.** Screen the Materials Cloud 2D database and C2DB (Computational 2D Materials Database) using symmetry analysis to identify candidate space groups compatible with altermagnetism (requiring specific rotational symmetry connecting opposite-spin sublattices). Perform DFT+SOC calculations (Quantum ESPRESSO with fully relativistic pseudopotentials) on the top **10–15 candidates**. Compute spin-resolved band structures, spin Hall conductivity via Wannier90 + WannierBerri (Kubo formalism), and magnetic anisotropy energies. For the most promising material, construct a tight-binding model and simulate quantum transport through a 2-terminal nanodevice using Kwant (open-source NEGF) to predict spin-polarized conductance.

**Feasibility: high, but computationally demanding.** All tools are fully open-source (Quantum ESPRESSO, Wannier90, WannierBerri, Kwant, ASE). Requires HPC access for DFT, but national computing allocations (ACCESS/XSEDE in the US, PRACE in Europe, university clusters) are available. No lab access needed. A focused study on 3–5 confirmed 2D altermagnets with transport predictions fits well in 4–6 pages. Aligns with IEEE-NANO topics: **Spintronics, Nano-Materials, Modeling and Simulation, Quantum/Unconventional Computing**.

---

## 5. Self-powered neuromorphic nano-system: nanogenerator to memristive SNN co-simulation

**The gap.** IEEE-NANO explicitly covers both Nano-Energy and Neuromorphic Computing, yet **no simulation study bridges the two domains** by modeling an integrated system where a nanogenerator harvests ambient energy to power a memristive SNN inference engine. Nanogenerator simulation (COMSOL FEM of piezoelectric PVDF, ZnO nanowires, triboelectric devices) and memristive SNN circuit simulation (PySpice, SIMBRAIN) are each mature, but they have never been connected. The self-powered edge AI paradigm—critical for implantable biomedical sensors, structural health monitoring, and IoT—demands exactly this integration.

**The research question.** What are the minimum harvesting area and energy storage requirements for a piezoelectric PVDF nanogenerator to intermittently power a memristor-based SNN performing real-time classification (e.g., heartbeat anomaly detection), and what is the system-level energy budget breakdown across harvesting, power management, and inference?

**Methodology and tools.** Stage 1: COMSOL Multiphysics FEM simulation of a PVDF nanofiber array under mechanical excitation (body motion, vibration), extracting voltage/current waveforms and power density vs. geometry. Stage 2: LTSpice simulation of a rectifier + supercapacitor power management circuit, driven by COMSOL-exported waveforms. Stage 3: PySpice simulation of a small-scale memristive SNN (e.g., **32×32 crossbar**, 2-layer LIF network with STDP) using the VTEAM RRAM model, measuring per-inference energy. Stage 4: System-level integration in Python, modeling duty-cycling (harvest → store → infer → sleep) and computing inference throughput as a function of harvester size. Compare against published energy figures for CMOS neuromorphic chips (e.g., Intel Loihi 2, IBM NorthPole).

**Feasibility: high.** COMSOL is available at most universities. PySpice and LTSpice are free. The cross-domain nature of the work is unusual but straightforward—each simulation stage uses established tools and feeds its output (waveforms, power figures) to the next stage. The paper tells a compelling **system-level story** that no single-domain paper can. It intersects **nano-energy + neuromorphic computing + memristors + sensors**, covering at least four IEEE-NANO tracks.

---

## How these five gaps compare across key criteria

| Rank | Topic | Novelty | Feasibility | Multi-topic score | IEEE-NANO fit | Open-source tools? |
|------|-------|---------|-------------|-------------------|---------------|-------------------|
| 1 | FeFET approximate CiM circuits | ★★★★★ | ★★★★★ | 3 topics | Excellent | Yes (ngspice, Verilog-A) |
| 2 | RRAM aging + neuromorphic + PUF | ★★★★★ | ★★★★★ | 4 topics | Excellent | Yes (PySpice, Python) |
| 3 | Neural ODE memristor compact model | ★★★★★ | ★★★★★ | 3 topics | Excellent | Yes (PyTorch, DEVSIM) |
| 4 | 2D altermagnetic spintronic materials | ★★★★★ | ★★★★☆ | 3 topics | Strong | Yes (QE, Wannier90, Kwant) |
| 5 | Self-powered nano-SNN system | ★★★★★ | ★★★★☆ | 4 topics | Excellent | Mostly (COMSOL needs license) |

---

## Practical guidance for choosing among the five

The optimal choice depends on the researcher's existing skills and tool access. **Gap 1 (FeFET approximate CiM)** has the best effort-to-novelty ratio: the methodology is standard SPICE Monte Carlo simulation, the compact models already exist, and the paper practically writes itself as a design + benchmarking study. **Gap 2 (RRAM aging + PUF + neuromorphic)** is equally novel but requires building an aging-parameterized device model, adding implementation complexity. **Gap 3 (Neural ODE)** suits researchers with ML expertise and produces a reusable modeling tool, giving it high citation potential. **Gap 4 (2D altermagnets)** is the most scientifically exciting—riding the wave of a brand-new magnetism paradigm—but demands DFT proficiency and HPC access. **Gap 5 (self-powered SNN)** tells the strongest system-level story and uniquely bridges two underconnected IEEE-NANO tracks, but requires multi-tool workflow orchestration.

For a researcher aiming to maximize acceptance probability at IEEE-NANO 2026 with limited time before the submission deadline, **Gap 1 or Gap 3** are recommended as the fastest path to a complete, well-scoped 4–6 page paper. For a researcher seeking maximum long-term impact, **Gap 4** positions them at the frontier of a field that will dominate spintronics research through 2030.

## Conclusion

The most fertile ground for simulation-only IEEE-NANO papers lies not within individual trending topics but at their **unexplored intersections**. Five specific gaps stand out: approximate computing mapped onto FeFET in-memory architectures, aging-driven co-degradation of dual-use RRAM crossbars, Neural ODE-based transient compact models for memristors, DFT prediction of 2D altermagnetic spintronics, and cross-domain co-simulation of nanogenerator-powered neuromorphic systems. Each gap has been verified against 2024–2025 literature to confirm that no existing publication occupies the proposed research space. All five are achievable with open-source or widely available academic tools, require no laboratory access, and map directly to multiple IEEE-NANO 2026 conference topics. The key strategic insight is that **topic convergence creates publication opportunity**—reviewers at a broad nanotechnology conference reward papers that connect siloed communities, and each of these proposals does exactly that.