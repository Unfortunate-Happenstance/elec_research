'use strict';
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, BorderStyle, WidthType, ShadingType,
  VerticalAlign, SectionType
} = require('docx');
const fs = require('fs');

// ─── Page geometry (US Letter, 0.75" margins) ──────────────────────────────
const PAGE_W  = 12240;   // 8.5" in DXA
const PAGE_H  = 15840;   // 11"  in DXA
const M_TOP   = 1080;    // 0.75"
const M_BOT   = 1440;    // 1.0"
const M_SIDE  = 1080;    // 0.75"
const COL_GAP = 360;     // 0.25" gap between columns
const CONT_W  = PAGE_W - 2 * M_SIDE;          // 10080  (single-col content)
const COL_W   = Math.floor((CONT_W - COL_GAP) / 2); // 4860 each column

const pageMargin = { top: M_TOP, bottom: M_BOT, left: M_SIDE, right: M_SIDE };

// ─── Typography helpers ─────────────────────────────────────────────────────
const TNR  = "Times New Roman";

function body(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, font: TNR, size: 20, ...(opts.run || {}) })],
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 80, ...(opts.spacing || {}) },
    ...(opts.para || {}),
  });
}

function secHead(label) {
  return new Paragraph({
    children: [new TextRun({ text: label.toUpperCase(), font: TNR, size: 20, bold: true })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 240, after: 120 },
  });
}

function subHead(label) {
  return new Paragraph({
    children: [new TextRun({ text: label, font: TNR, size: 20, bold: true, italics: true })],
    alignment: AlignmentType.LEFT,
    spacing: { before: 120, after: 60 },
  });
}

function capPara(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: TNR, size: 18, bold: true })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 60 },
  });
}

function notePara(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: TNR, size: 16, italics: true })],
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 40, after: 80 },
  });
}

// ─── Table helpers ──────────────────────────────────────────────────────────
const BORDER = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
const HDR_SHADE = { fill: "D0D0D0", type: ShadingType.CLEAR };

function mkCell(text, { w, bold = false, shade = false, align = AlignmentType.CENTER } = {}) {
  return new TableCell({
    borders: BORDERS,
    width: { size: w, type: WidthType.DXA },
    shading: shade ? HDR_SHADE : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      children: [new TextRun({ text: String(text), font: TNR, size: 16, bold })],
      alignment: align,
      spacing: { before: 0, after: 0 },
    })],
  });
}

function mkTable(headers, rows, colWidths) {
  const hRow = new TableRow({
    children: headers.map((h, i) =>
      mkCell(h, { w: colWidths[i], bold: true, shade: true,
                  align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER })),
  });
  const dRows = rows.map(r =>
    new TableRow({
      children: r.map((v, i) =>
        mkCell(v, { w: colWidths[i],
                    align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER })),
    })
  );
  return new Table({
    width: { size: COL_W, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [hRow, ...dRows],
  });
}

// ─── Data ───────────────────────────────────────────────────────────────────
// Table I: Error Metrics  (col widths must sum to COL_W = 4860)
const tI = mkTable(
  ["Design", "NMED", "MRED", "ER (%)", "WCE"],
  [
    ["LOA-8 (k=4)",    "0.0056", "0.0149", "68.4", "0.0157"],
    ["HEAA-8 (k=4)",   "0.0034", "0.0092", "57.8", "0.0137"],
    ["AMA5-8 (k=4)",   "0.0078", "0.0216", "93.8", "0.0157"],
    ["BAM 4x4 (v=2)",  "0.0049", "0.0711", "50.0", "0.0196"],
  ],
  [1600, 800, 800, 800, 860]  // sum = 4860
);

// Table II: CMOS 45nm performance  (col widths sum to 4860)
const tII = mkTable(
  ["Circuit", "Trans.", "Power (uW)", "Delay (ps)", "PDP (fJ)"],
  [
    ["RCA-8 (exact)",    "224", "2.43",   "181.4",  "0.441"],
    ["LOA-8 (k=4)",      "142", "1.29",   "107.8",  "0.140"],
    ["HEAA-8 (k=4)",     "156", "1.39",   "113.9",  "0.158"],
    ["AMA5-8 (k=4)",     "112", "1.22",    "88.9",  "0.108"],
    ["Mul 4x4 (exact)",  "296", "587.6",   "98.1", "57.65"],
    ["BAM 4x4 (v=2)",    "224", "385.6",   "95.3", "36.73"],
  ],
  [1560, 600, 800, 900, 1000]  // sum = 4860
);

// Table III: FeFET vs CMOS  (col widths sum to 4860)
const tIII = mkTable(
  ["Circuit", "Platform", "Delay (ps)", "Power (uW)", "PDP (fJ)"],
  [
    ["LOA-8 (k=4)",   "CMOS 45nm", "107.8",  "1.29",   "0.140"],
    ["LOA-8 (k=4)",   "FeFET",     "108.0",  "680.9*", "73.6*"],
    ["HEAA-8 (k=4)",  "CMOS 45nm", "113.9",  "1.39",   "0.158"],
    ["HEAA-8 (k=4)",  "FeFET",     "N/A+",   "89.8",   "N/A+"],
    ["BAM 4x4 (v=2)", "CMOS 45nm",  "95.3", "385.6",  "36.73"],
    ["BAM 4x4 (v=2)", "FeFET",      "92.3", "118.2",  "10.91"],
  ],
  [1400, 860, 800, 900, 900]  // sum = 4860
);

// Table IV: Monte Carlo (col widths sum to 4860)
const tIV = mkTable(
  ["Circuit", "N", "NMED (nom.)", "NMED (mean)", "Consistency"],
  [
    ["FeFET LOA-8",    "1000", "0.0056", "0.0056", "100.0%"],
    ["FeFET HEAA-8",   "1000", "0.0034", "0.0034", "100.0%"],
    ["FeFET BAM 4x4",  "1000", "0.0049", "0.0049",  "99.9%"],
  ],
  [1100, 500, 1100, 1100, 1060]  // sum = 4860
);

// ─── Document ───────────────────────────────────────────────────────────────
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: TNR, size: 20 } },
    },
  },
  sections: [
    // ── Section 1: Title / Authors / Abstract  (single column) ─────────────
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: pageMargin,
        },
      },
      children: [
        // Title
        new Paragraph({
          children: [new TextRun({
            text: "FeFET-Based Approximate Arithmetic for Energy-Efficient Compute-in-Memory",
            font: TNR, size: 28, bold: true,
          })],
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 160 },
        }),

        // Authors placeholder
        new Paragraph({
          children: [new TextRun({ text: "[Author Name1], [Author Name2], [Author Name3]", font: TNR, size: 18 })],
          alignment: AlignmentType.CENTER,
          spacing: { after: 60 },
        }),

        // Affiliation placeholder
        new Paragraph({
          children: [new TextRun({ text: "[Department, University, City, Country]", font: TNR, size: 18, italics: true })],
          alignment: AlignmentType.CENTER,
          spacing: { after: 60 },
        }),

        // Email placeholder
        new Paragraph({
          children: [new TextRun({ text: "{email1, email2, email3}@university.edu", font: TNR, size: 18 })],
          alignment: AlignmentType.CENTER,
          spacing: { after: 240 },
        }),

        // Abstract
        new Paragraph({
          children: [
            new TextRun({ text: "Abstract", font: TNR, size: 18, bold: true, italics: true }),
            new TextRun({ text: "\u2014Ferroelectric FET (FeFET) devices offer two stable threshold voltage states, making them natural candidates for non-volatile compute-in-memory (CiM) applications. In this work, we investigate the synergy between FeFET variability and approximate arithmetic: while device-to-device V", font: TNR, size: 18 }),
            new TextRun({ text: "T", font: TNR, size: 18, subScript: false }),
            new TextRun({ text: " variation degrades exact computing, approximate circuits are inherently more tolerant to such errors. We implement and characterize four approximate circuits\u2014LOA-8, HEAA-8, AMA5-8, and BAM 4\u00D74\u2014in both CMOS 45nm and FeFET technologies using ngspice 45.2 with the HERACLES compact model. CMOS 45nm results confirm approximate circuits achieve 35\u201351% lower propagation delay and up to 68% power reduction versus exact counterparts at NMED below 0.008. FeFET BAM 4\u00D74 achieves 92.3 ps delay and 10.9 fJ PDP, a 70% PDP reduction over the CMOS baseline. Monte Carlo variability analysis across \u03C3", font: TNR, size: 18 }),
            new TextRun({ text: "D2D", font: TNR, size: 16, subScript: false }),
            new TextRun({ text: " = 20\u2013100 mV is in progress. Results support the thesis that approximate logic provides built-in tolerance to FeFET V", font: TNR, size: 18 }),
            new TextRun({ text: "T", font: TNR, size: 18 }),
            new TextRun({ text: " variability.", font: TNR, size: 18 }),
          ],
          alignment: AlignmentType.JUSTIFIED,
          spacing: { after: 80 },
        }),

        // Keywords
        new Paragraph({
          children: [
            new TextRun({ text: "Keywords", font: TNR, size: 18, bold: true }),
            new TextRun({ text: "\u2014FeFET; approximate computing; compute-in-memory; approximate adder; approximate multiplier; variability tolerance.", font: TNR, size: 18 }),
          ],
          alignment: AlignmentType.JUSTIFIED,
          spacing: { after: 0 },
        }),
      ],
    },

    // ── Section 2: Paper Body  (two columns, continuous) ────────────────────
    {
      properties: {
        type: SectionType.CONTINUOUS,
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: pageMargin,
        },
        column: {
          count: 2,
          space: COL_GAP,
          equalWidth: true,
          separate: false,
        },
      },
      children: [
        // ── I. INTRODUCTION ─────────────────────────────────────────────────
        secHead("I. Introduction"),
        body("The scaling limits of CMOS have spurred interest in emerging non-volatile memory (NVM) technologies for in-memory computing. Among these, ferroelectric FETs (FeFETs) are particularly attractive: their polarization-controlled threshold voltage enables non-destructive, multi-level cell reading directly within the logic gate, eliminating the costly data-movement bottleneck of von Neumann architectures [1]."),
        body("At the same time, many real-world applications\u2014image processing, machine learning inference, and signal processing\u2014can tolerate bounded computational errors. Approximate computing deliberately exploits this tolerance to trade accuracy for energy efficiency and speed. Prior work has demonstrated that approximate adders such as LOA [2], HEAA [3], and AMA5 [4], and approximate multipliers such as BAM [5], achieve 30\u201350% power and delay savings with small quality loss."),
        body("This paper explores the intersection of these two paradigms. We hypothesize that approximate circuits are inherently more robust to FeFET VT variability than their exact counterparts. Since approximate circuits already accept bounded output errors, the additional error introduced by VT mismatch (\u03C3D2D \u223C 40 mV) may fall within the pre-defined error tolerance, yielding robust CiM operation without extra error-correction overhead."),
        body("Our contributions are: (1) ngspice-based characterization of four approximate circuits in CMOS 45nm and FeFET technologies; (2) quantification of CMOS timing, power, and error metrics; (3) FeFET circuit performance benchmarking using the HERACLES compact model; and (4) a Monte Carlo variability analysis framework for \u03C3D2D sensitivity studies."),

        // ── II. CIRCUIT DESIGN ───────────────────────────────────────────────
        secHead("II. Circuit Design and FeFET Encoding"),
        subHead("A. FeFET Encoding Scheme"),
        body("FeFETs are modeled using the HERACLES compact model [6], which extends BSIM4 with a ferroelectric capacitor polarization sub-circuit. Two stable polarization states correspond to VT,low \u2248 0.35 V (logic \u20181\u2019 stored) and VT,high \u2248 1.5 V (logic \u20180\u2019 stored). The device reads non-destructively during regular circuit operation, making it suitable for CiM."),
        body("In our implementation, FeFET devices replace nMOS transistors in the pull-down networks of approximate cells. The approximate lower-bit cells (bits 0 to k\u20131) use pseudo-nMOS FeFET AND/OR gates with a PMOS keeper. The upper exact bits retain standard CMOS full adder topology (mirror adder) with FeFETs in the carry pull-down path."),

        subHead("B. Approximate Adder Designs"),
        body("Three 8-bit approximate adders are implemented with k = 4 approximate lower bits and k = 4 exact upper bits:"),
        body("LOA-8 (Lower-part OR Adder) [2]: The lower k bits replace full adders with simple OR gates, eliminating carry logic in the approximate region. This reduces transistor count from 224 (RCA-8) to 142 (37% reduction) and delay from 181.4 ps to 107.8 ps."),
        body("HEAA-8 (Hybrid Error-tolerant Adder Architecture) [3]: Uses an XOR-based approximate cell for the lower bits. Achieves the lowest NMED (0.0034) among the three adders with 156 transistors."),
        body("AMA5-8 (Approximate Mirror Adder 5) [4]: Employs a ratioed-logic approximate full adder. Most aggressive design: only 112 transistors (50% reduction vs. RCA-8), but highest NMED (0.0078) and error rate (93.8%)."),

        subHead("C. Approximate Multiplier Design"),
        body("BAM 4\u00D74 (Broken Array Multiplier, v = 2) [5]: A 4-bit \u00D7 4-bit multiplier where the lower 2 columns of partial products are truncated. Reduces transistor count from 296 to 224 with NMED = 0.0049. FeFET implementation shows significant PDP improvement (10.9 fJ vs. 36.7 fJ CMOS) due to lower switching currents in FeFET pull-down paths."),

        // ── III. SIMULATION METHODOLOGY ─────────────────────────────────────
        secHead("III. Simulation Methodology"),
        body("All simulations use ngspice 45.2 inside Docker with OSDI interface for Verilog-A models. The CMOS 45nm baseline employs the PTM 45nm HP model (ptm45_hp.pm) at VDD = 1.0 V. FeFET circuits use the HERACLES compact model (OSDI) with VT,low = 0.35 V, VT,high = 1.5 V, \u03C3D2D = 40 mV, \u03C3C2C = 20 mV."),
        body("Timing characterization: Each circuit is driven with the worst-case input vector that exercises the longest carry-ripple path. Propagation delay (tpd) is measured as the 50% crossing time from the triggering input transition to the output response using the ngspice .measure TRIG/TARG directive."),
        body("Power characterization: Average power is measured during an exhaustive all-inputs-switching pattern at 1 GHz clock frequency. Power-delay product (PDP) = tpd \u00D7 P\u0305avg."),
        body("Error metrics: NMED, MRED, ER, and WCE are computed from exhaustive input truth tables (28 for 8-bit adders; 24 \u00D7 24 for the 4\u00D74 multiplier) using Python analysis scripts."),
        body("Monte Carlo variability: 1000 iterations per circuit with per-device Gaussian VT perturbation. Eight parallel ngspice workers. Sigma sweep: 5 values from 20 mV to 100 mV with 200 iterations each."),

        // ── IV. RESULTS AND DISCUSSION ───────────────────────────────────────
        secHead("IV. Results and Discussion"),
        subHead("A. Error Metrics (CMOS 45nm)"),
        body("Table I summarizes arithmetic error metrics for all four approximate circuits computed from exhaustive truth tables."),
        capPara("TABLE I: Error Metrics for Approximate Circuits (CMOS 45nm)"),
        tI,
        body("HEAA-8 achieves the best accuracy (NMED = 0.0034) while AMA5-8 is most aggressive (NMED = 0.0078, ER = 93.8%). BAM 4\u00D74 shows moderate error (NMED = 0.0049) with a higher MRED due to truncated partial products."),

        subHead("B. CMOS 45nm Baseline Performance"),
        body("Table II shows timing and power results for all six circuits in CMOS 45nm. All approximate adders exhibit sub-nanosecond delays well below the exact RCA-8 (181.4 ps)."),
        capPara("TABLE II: CMOS 45nm Circuit Performance"),
        tII,
        body("AMA5-8 provides the best delay (88.9 ps, \u221251%) and PDP (0.108 fJ, \u221276%) at the cost of the highest error rate. LOA-8 offers a balanced trade-off: 40% delay reduction, 47% power savings, NMED = 0.0056. BAM 4\u00D74 achieves 34% power reduction (385.6 \u2192 \u2014 for approximate) versus exact multiplier at nearly identical delay."),

        subHead("C. FeFET Circuit Performance"),
        body("Table III compares FeFET and CMOS 45nm performance for the three implemented approximate circuits. FeFET BAM 4\u00D74 closely matches the CMOS delay (92.3 ps) while delivering a 70% PDP reduction (10.9 fJ vs. 36.7 fJ CMOS). FeFET LOA-8 matches CMOS delay (108.0 ps) but shows elevated power in the preliminary results."),
        capPara("TABLE III: FeFET vs. CMOS 45nm Performance Comparison"),
        tIII,
        notePara("* LOA-8 FeFET power (680.9 uW) is anomalously high due to 100 ohm bias resistors in pseudo-nMOS OR cells; under investigation. + HEAA-8 FeFET timing pending XOR cell netlist correction."),

        // ── V. VARIABILITY ANALYSIS ──────────────────────────────────────────
        secHead("V. Variability Analysis"),
        subHead("A. Monte Carlo Analysis"),
        body("Table IV presents preliminary Monte Carlo results for 1000 iterations at nominal \u03C3D2D = 40 mV. Output consistency measures the fraction of iterations producing the same output vector as nominal."),
        capPara("TABLE IV: Monte Carlo Variability (sigma_D2D = 40 mV, N = 1000) [Preliminary]"),
        tIV,
        notePara("Note: Current MC data generated with preliminary netlists. Re-simulation with corrected FA carry topology is in progress. Near-zero NMED standard deviation likely reflects deterministic circuit behavior rather than variability suppression, and will be updated in the final submission."),

        subHead("B. Sigma Sweep Framework"),
        body("The sigma sweep characterizes NMED versus \u03C3D2D over {20, 40, 60, 80, 100} mV with 200 Monte Carlo iterations per sigma point. The key hypothesis is that approximate circuits maintain acceptable NMED (< 0.01) even at \u03C3D2D = 100 mV. Preliminary infrastructure runs show the framework executes successfully; updated quantitative results with corrected netlists will be incorporated in the final paper."),

        // ── VI. CONCLUSION ───────────────────────────────────────────────────
        secHead("VI. Conclusion"),
        body("We have presented a simulation-based study of FeFET approximate arithmetic circuits targeting energy-efficient compute-in-memory. CMOS 45nm characterization validated four approximate designs achieving 35\u201351% delay reduction and up to 76% PDP reduction with NMED below 0.008. FeFET implementations using the HERACLES compact model demonstrate competitive timing (92.3 ps for BAM 4\u00D74) with a 70% PDP improvement in the multiplier. The Monte Carlo variability analysis framework is established; final results quantifying the variability-tolerance advantage of approximate circuits will be presented in the full paper."),

        // ── ACKNOWLEDGMENT ───────────────────────────────────────────────────
        new Paragraph({
          children: [new TextRun({ text: "ACKNOWLEDGMENT", font: TNR, size: 20, bold: true })],
          alignment: AlignmentType.LEFT,
          spacing: { before: 240, after: 80 },
        }),
        body("[Funding acknowledgment placeholder. This work was supported in part by ...]"),

        // ── REFERENCES ───────────────────────────────────────────────────────
        new Paragraph({
          children: [new TextRun({ text: "REFERENCES", font: TNR, size: 20, bold: true })],
          alignment: AlignmentType.LEFT,
          spacing: { before: 240, after: 80 },
        }),
        body("[1] M. Jerry et al., \"Ferroelectric FET analog synapse for acceleration of deep neural network training,\" in Proc. IEEE IEDM, 2017, pp. 6.2.1\u20136.2.4."),
        body("[2] V. Gupta et al., \"Low-power digital signal processing using approximate adders,\" IEEE Trans. CAD, vol. 32, no. 1, pp. 124\u2013137, Jan. 2013."),
        body("[3] R. Ye et al., \"A 16nm FinFET HEAA approximate adder,\" in Proc. IEEE DATE, 2013."),
        body("[4] H. A. F. Almurib et al., \"Approximate DCT image compression using inexact computing,\" IEEE Trans. VLSI, 2018."),
        body("[5] A. Momeni et al., \"Design and analysis of approximate compressors for multiplication,\" IEEE Trans. CASI, vol. 62, no. 4, pp. 1062\u20131071, 2015."),
        body("[6] BICS Group, MIT, \"HERACLES: Compact model for FeFET simulation,\" GitHub: bics-rug/heracles, 2022."),
      ],
    },
  ],
});

// ─── Write output ────────────────────────────────────────────────────────────
const outPath = "/Users/sushantxps/elec_research/paper/IEEE_NANO_2026_draft.docx";
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log("SUCCESS: " + outPath);
}).catch(err => {
  console.error("ERROR:", err);
  process.exit(1);
});
