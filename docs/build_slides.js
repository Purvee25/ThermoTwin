// Builds docs/ThermoTwin_architecture.pptx and docs/ThermoTwin_presentation.pptx.
// Run from the repo root: node docs/build_slides.js  (needs pptxgenjs on NODE_PATH)
const path = require("path");
const pptxgen = require("pptxgenjs");

const OUT = __dirname;
const IMG = path.join(__dirname, "img");
const C = {
  ink: "1C1B19", muted: "6B675F", line: "D9D5CD", soft: "F0EEEA", white: "FFFFFF",
  heat: "B4461E", heatSoft: "F6E3DA", blue: "1F5FA8", blueSoft: "E3ECF7",
  green: "1D8A5B", greenSoft: "E1F1E9", red: "C2322B", amber: "C98A12", dark: "1C1B19",
};
const HEAD = "Cambria";
const BODY = "Calibri";

const text = (slide, value, opts) =>
  slide.addText(value, { fontFace: BODY, color: C.ink, margin: 0, isTextBox: true, ...opts });

function title(slide, value, sub) {
  text(slide, value, { x: 0.5, y: 0.35, w: 9, h: 0.6, fontFace: HEAD, fontSize: 28, bold: true });
  if (sub) text(slide, sub, { x: 0.5, y: 0.95, w: 9, h: 0.35, fontSize: 13, color: C.muted });
}

function card(slide, x, y, w, h, fill = C.soft) {
  slide.addShape("roundRect", { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill } });
}

function badge(slide, x, y, label, fill = C.heat) {
  slide.addShape("ellipse", { x, y, w: 0.42, h: 0.42, fill: { color: fill }, line: { color: fill } });
  text(slide, label, { x, y, w: 0.42, h: 0.42, fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle" });
}

function footer(slide, value) {
  text(slide, value, { x: 0.5, y: 5.22, w: 9, h: 0.25, fontSize: 8.5, color: C.muted });
}


// Bar charts drawn from shapes: pptxgenjs chart parts do not render in Keynote/PDF export.
function shapeBars(slide, { x, y, w, h, labels, values, colors, max, format, horizontal, title: heading }) {
  if (heading) text(slide, heading, { x, y, w, h: 0.3, fontSize: 12, bold: true });
  const top = heading ? y + 0.4 : y;
  const height = heading ? h - 0.4 : h;
  const n = values.length;
  if (horizontal) {
    const labelW = 1.75;
    const valueW = 0.55;
    const trackW = w - labelW - valueW;
    const rowH = height / n;
    values.forEach((v, i) => {
      const cy = top + i * rowH;
      text(slide, labels[i], { x, y: cy, w: labelW - 0.1, h: rowH, fontSize: 11.5, valign: "middle" });
      const barW = Math.max(0.02, (v / max) * trackW);
      slide.addShape("rect", { x: x + labelW, y: cy + rowH * 0.2, w: barW, h: rowH * 0.6, fill: { color: colors[i] }, line: { color: colors[i] } });
      text(slide, format(v), { x: x + labelW + barW + 0.06, y: cy, w: valueW + 0.3, h: rowH, fontSize: 11.5, bold: true, valign: "middle" });
    });
    return;
  }
  const labelH = 0.4;
  const valueH = 0.4;
  const plotH = height - labelH - valueH;
  const slotW = w / n;
  const barW = slotW * 0.5;
  values.forEach((v, i) => {
    const bx = x + i * slotW + (slotW - barW) / 2;
    const bh = Math.max(0.02, (v / max) * plotH);
    const by = top + valueH + plotH - bh;
    slide.addShape("rect", { x: bx, y: by, w: barW, h: bh, fill: { color: colors[i] }, line: { color: colors[i] } });
    text(slide, format(v), { x: x + i * slotW, y: by - valueH, w: slotW, h: valueH, fontSize: 20, bold: true, align: "center", valign: "bottom", fontFace: HEAD });
    text(slide, labels[i], { x: x + i * slotW, y: top + valueH + plotH + 0.05, w: slotW, h: labelH, fontSize: 12, align: "center", valign: "top" });
  });
  slide.addShape("line", { x, y: top + valueH + plotH, w, h: 0, line: { color: C.line, width: 1 } });
}

// ---------- Architecture diagram (shared) ----------
function box(slide, x, y, w, h, head, body, fill, stroke, headColor = C.ink) {
  slide.addShape("roundRect", { x, y, w, h, rectRadius: 0.06, fill: { color: fill }, line: { color: stroke, width: 1 } });
  text(slide, [
    { text: head, options: { bold: true, fontSize: 10.5, color: headColor, breakLine: true } },
    { text: body, options: { fontSize: 8.5, color: C.muted } },
  ], { x: x + 0.1, y: y + 0.05, w: w - 0.2, h: h - 0.1, valign: "middle" });
}

function arrow(slide, x1, y1, x2, y2, color = C.muted, dashed = false) {
  slide.addShape("line", {
    x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipH: x2 < x1, flipV: y2 < y1,
    line: { color, width: 1.25, endArrowType: "triangle", dashType: dashed ? "dash" : "solid" },
  });
}

function columnLabel(slide, x, w, label) {
  text(slide, label.toUpperCase(), { x, y: 1.28, w, h: 0.25, fontSize: 9, bold: true, color: C.muted, charSpacing: 2 });
}

function drawArchitecture(slide) {
  title(slide, "ThermoTwin architecture", "Hybrid physics + ML twin: the medication record changes the physiology model, not just the score");

  columnLabel(slide, 0.5, 2.2, "Data streams");
  const data = [
    ["Static EHR (synthetic)", "BP meds by class, eGFR history, NSAIDs, age, BMI", C.white, C.line],
    ["Wearable stream", "1-min heart rate + activity (JOS-3 simulated shifts)", C.white, C.line],
    ["Weather", "Open-Meteo archive: Delhi heatwave, May 2024", C.white, C.line],
    ["Real heat trials", "PROSPIE (22 people, 99 trials): validation only", C.soft, C.line],
  ];
  data.forEach(([h, b, fill, stroke], i) => box(slide, 0.5, 1.58 + i * 0.8, 2.2, 0.68, h, b, fill, stroke));

  columnLabel(slide, 3.15, 2.75, "Twin engine (Python)");
  const engine = [
    ["1  ECTemp Kalman filter", "Core temperature from heart rate"],
    ["2  Medication correction", "β-blocker: un-blunt HR, widen noise"],
    ["3  Personal bias learning", "Thermometer readings from past shifts"],
    ["4  60-min forecaster", "Gagge physics + gradient boosting"],
  ];
  engine.forEach(([h, b], i) => box(slide, 3.15, 1.58 + i * 0.8, 2.75, 0.68, h, b, C.blueSoft, C.blue, C.blue));
  for (let i = 0; i < 3; i++) arrow(slide, 4.52, 2.26 + i * 0.8, 4.52, 2.38 + i * 0.8, C.blue);

  columnLabel(slide, 6.35, 1.6, "Service");
  box(slide, 6.35, 1.58, 1.6, 1.48, "FastAPI", "/patients\n/timeline\n/whatif\n/review", C.white, C.line);
  box(slide, 6.35, 3.18, 1.6, 1.48, "Review rules", "Triple whammy, eGFR decline, β-blocker masking, heat strain", C.heatSoft, C.heat, C.heat);

  columnLabel(slide, 8.3, 1.3, "Users");
  box(slide, 8.3, 1.58, 1.2, 1.48, "Dashboard", "React: live twin, what-if, review", C.greenSoft, C.green, C.green);
  box(slide, 8.3, 3.18, 1.2, 1.48, "PHC doctor", "Pre-summer medication review", C.white, C.line);

  [0, 1, 2].forEach((i) => arrow(slide, 2.7, 1.92 + i * 0.8, 3.15, 1.92 + i * 0.8));
  arrow(slide, 2.7, 4.32, 3.15, 2.1, C.muted, true);
  arrow(slide, 5.9, 2.32, 6.35, 2.32);
  arrow(slide, 5.9, 3.92, 6.35, 3.92);
  arrow(slide, 7.95, 2.32, 8.3, 2.32);
  arrow(slide, 8.9, 3.06, 8.9, 3.18);

  card(slide, 0.5, 4.82, 9.0, 0.36, C.soft);
  text(slide, "Deploy: Docker Compose (non-root API with health check · nginx serves dashboard and proxies /api)    ·    Quality: pytest suite, participant-held-out real-data validation, multi-seed evaluation", {
    x: 0.65, y: 4.82, w: 8.7, h: 0.36, fontSize: 8.5, color: C.ink, valign: "middle",
  });
}

function buildArchitecture() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "ThermoTwin architecture";
  const slide = pres.addSlide();
  slide.background = { color: C.white };
  drawArchitecture(slide);
  slide.addNotes("Data flows left to right. The EHR medication list switches the twin's physiology model (step 2). PROSPIE real data is used only for validation (dashed arrow).");
  return pres.writeFile({ fileName: path.join(OUT, "ThermoTwin_architecture.pptx") });
}

// ---------- Presentation ----------
function buildDeck() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "ThermoTwin";

  // 1. Title
  let s = pres.addSlide();
  s.background = { color: C.dark };
  text(s, "Happiest Health · Digital Twin Challenge 2026", { x: 0.6, y: 0.6, w: 8.8, h: 0.3, fontSize: 12, color: "E0774A", bold: true, charSpacing: 1 });
  text(s, "ThermoTwin", { x: 0.6, y: 1.35, w: 8.8, h: 1.0, fontFace: HEAD, fontSize: 54, bold: true, color: C.white });
  text(s, "A hypertension digital twin that knows how your medicines handle India's heat", { x: 0.6, y: 2.4, w: 8.2, h: 0.8, fontSize: 20, color: "D8D4CC" });
  text(s, "[Team name] · [College / incubator]", { x: 0.6, y: 4.6, w: 8.8, h: 0.3, fontSize: 12, color: "A19C92" });
  s.addNotes("Introduce the team. One line: ThermoTwin predicts heat-triggered crises in people with hypertension, and corrects for the medicines that fool normal wearables.");

  // 2. Problem
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "Heat is hiding inside heart deaths", "India's heat toll is massively under-counted, and hypertension sits at the centre of it");
  const stats = [
    ["14", "official heatstroke deaths in India, 2025", C.muted],
    ["~30,000", "estimated excess deaths from a single five-day heatwave", C.red],
    ["315 M", "Indian adults living with hypertension", C.heat],
    ["~380 M", "workers whose jobs expose them to heat", C.amber],
  ];
  stats.forEach(([big, label, color], i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.55, 2.1, 2.6);
    text(s, big, { x: x + 0.15, y: 1.8, w: 1.8, h: 0.9, fontFace: HEAD, fontSize: 34, bold: true, color });
    text(s, label, { x: x + 0.15, y: 2.75, w: 1.8, h: 1.2, fontSize: 13, color: C.ink, valign: "top" });
  });
  text(s, "Many heat deaths are recorded as cardiac arrest. Blood-pressure medicines change how the body handles heat, but no tool connects a patient's record to today's weather.", {
    x: 0.5, y: 4.35, w: 9, h: 0.6, fontSize: 13, color: C.ink,
  });
  footer(s, "Sources: NCDC via Deccan Herald (2025); Frontiers in Environmental Health 2026; ICMR-INDIAB (Lancet Diabetes Endocrinol 2023); Lancet Countdown India 2025.");
  s.addNotes("Lead with the gap between 14 official deaths and about 30,000 excess deaths. Heat hides in cardiac-arrest counts, and hypertension is where heat and heart risk meet.");

  // 3. Blind spot
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "The blind spot: beta-blockers fool wearables", "Heat models read core temperature from heart rate, and beta-blockers stop heart rate rising");
  text(s, [
    { text: "Wearable heat models assume heart rate rises with core temperature.", options: { bullet: true, breakLine: true } },
    { text: "Beta-blockers blunt that rise, so estimates read low for exactly the patients at risk.", options: { bullet: true, breakLine: true } },
    { text: "ThermoTwin reads the medication record and corrects the physiology before estimating.", options: { bullet: true } },
  ], { x: 0.5, y: 1.55, w: 4.1, h: 2.4, fontSize: 15, paraSpaceAfter: 10, valign: "top" });
  text(s, "Tested on real heat-trial data (PROSPIE) with a simulated beta-blocker effect on heart rate.", { x: 0.5, y: 4.2, w: 4.1, h: 0.6, fontSize: 11, color: C.muted, italic: true });
  shapeBars(s, {
    x: 5.2, y: 1.3, w: 4.2, h: 1.9, labels: ["HR model", "ThermoTwin"], values: [18, 62],
    colors: [C.muted, C.heat], max: 100, format: (v) => `${v}%`, title: "Danger minutes (≥ 38 °C) caught",
  });
  shapeBars(s, {
    x: 5.2, y: 3.3, w: 4.2, h: 1.6, labels: ["HR model", "ThermoTwin"], values: [0, 8],
    colors: [C.muted, C.blue], max: 20, format: (v) => `${v}%`, title: "False-alarm rate",
  });
  s.addNotes("This is the core insight. On real heat-trial data, a plain heart-rate model caught 18% of dangerous minutes for a beta-blocked patient. ThermoTwin caught 62%, with an 8% false-alarm rate. The false-alarm chart shows the trade-off: we catch more but do raise more alerts per shift.");

  // 4. Solution
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "ThermoTwin in one slide", "A digital twin of a hypertensive outdoor worker, updated minute by minute");
  const cols = [
    ["Condition", "Hypertension, with the medicines that treat it (β-blockers, ACE-i/ARB, CCB, diuretics)", C.heat],
    ["Adverse event", "Core temperature ≥ 38 °C: now, and forecast 60 minutes ahead", C.red],
    ["Inputs", "Static EHR + 1-minute wearable heart rate and activity + weather", C.blue],
    ["Users", "PHC doctor (dashboard, pre-summer review) and worker (rest alert)", C.green],
  ];
  cols.forEach(([h, b, color], i) => {
    const y = 1.5 + i * 0.88;
    badge(s, 0.5, y + 0.1, String(i + 1), color);
    text(s, h, { x: 1.1, y, w: 2.2, h: 0.62, fontFace: HEAD, fontSize: 17, bold: true, valign: "middle" });
    text(s, b, { x: 3.2, y, w: 6.3, h: 0.62, fontSize: 14, valign: "middle" });
  });
  s.addNotes("The condition is hypertension, which the brief names directly. Heat is the stressor. The twin fuses the static record with the live stream and predicts a specific event: core temperature reaching 38 degrees.");

  // 5. Architecture
  s = pres.addSlide();
  s.background = { color: C.white };
  drawArchitecture(s);
  s.addNotes("Walk left to right: data streams, the four-step twin engine, the API and review rules, then the dashboard. PROSPIE is validation only.");

  // 6. How the twin works
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "How the twin thinks", "Physics first, then personalisation, then forecasting");
  const steps = [
    ["Estimate", "ECTemp Kalman filter turns 1-minute heart rate into core temperature (Buller et al. 2013)."],
    ["Correct", "If the EHR lists a β-blocker, un-blunt heart rate with population priors and widen uncertainty."],
    ["Personalise", "Learn each worker's bias from a few thermometer readings on earlier shifts."],
    ["Forecast", "Gagge two-node physics + gradient boosting predict ≥ 38 °C within 60 minutes."],
  ];
  steps.forEach(([h, b], i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.55, 2.1, 2.9, i === 1 ? C.heatSoft : C.soft);
    badge(s, x + 0.2, 1.75, String(i + 1), i === 1 ? C.heat : C.blue);
    text(s, h, { x: x + 0.2, y: 2.3, w: 1.75, h: 0.45, fontFace: HEAD, fontSize: 18, bold: true });
    text(s, b, { x: x + 0.2, y: 2.8, w: 1.75, h: 1.55, fontSize: 12, valign: "top" });
  });
  text(s, "Honest by design: ground truth comes from a different physiology model (JOS-3) than the twin uses, and each patient's true drug response is hidden from it.", {
    x: 0.5, y: 4.6, w: 9, h: 0.45, fontSize: 11.5, color: C.muted, italic: true,
  });
  s.addNotes("Step 2 is where the record changes the physics. To avoid circular results, the simulator uses JOS-3 and the twin uses ECTemp and Gagge, and each patient's true drug response is hidden.");

  // 7. Real-data evidence
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "Validated on real heat trials", "PROSPIE: 22 participants, 99 trials, rectal core temperature, held-out participants");
  card(s, 0.5, 1.55, 2.6, 2.9, C.blueSoft);
  text(s, "0.32 °C", { x: 0.7, y: 1.85, w: 2.3, h: 0.8, fontFace: HEAD, fontSize: 36, bold: true, color: C.blue });
  text(s, "core-temperature error of our heart-rate engine on real people, in line with the published ~0.3 °C", { x: 0.7, y: 2.7, w: 2.25, h: 1.5, fontSize: 12.5, valign: "top" });
  const rows = [
    [{ text: "β-blocker scenario (real data)", options: { bold: true } }, { text: "Error", options: { bold: true } }, { text: "Danger caught", options: { bold: true } }, { text: "False alarms", options: { bold: true } }],
    ["Heart-rate model", "0.63 °C", "18%", "0%"],
    ["ThermoTwin (medication-aware)", "0.39 °C", "62%", "8%"],
    ["+ learned personal bias *", "0.37 °C", "79%", "38%"],
  ];
  s.addTable(rows, {
    x: 3.4, y: 1.6, w: 6.1, colW: [2.65, 1.1, 1.25, 1.1], fontFace: BODY, fontSize: 12, color: C.ink,
    border: { type: "solid", pt: 0.75, color: C.line }, fill: { color: C.white }, rowH: 0.45, valign: "middle",
  });
  text(s, "* Separate run with a different random drug response: 0.44 → 0.37 °C and 59% → 79% caught, but false alarms rise 13% → 38%, a trade-off we report. Skin-temperature fusion gave no real gain, so we don't claim it.", {
    x: 3.4, y: 3.65, w: 6.1, h: 0.9, fontSize: 12, color: C.muted, italic: true,
  });
  footer(s, "PROSPIE dataset, Loughborough University (CC BY-NC 4.0). The beta-blocker effect is simulated on real heart rate; participants were healthy volunteers.");
  s.addNotes("Emphasise that these are real core temperatures. Our filter matches the published accuracy. The medication-aware twin roughly triples detection for beta-blocked patients.");

  // 8. Forecast results
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "60-minute forecast on a real Delhi heatwave", "200 simulated workers on May–June 2024 weather (peaks of 46 °C), tested on unseen patients, 3 seeds");
  shapeBars(s, {
    x: 0.5, y: 1.45, w: 6.2, h: 3.6, horizontal: true, max: 1, format: (v) => v.toFixed(2),
    title: "AUROC, mean of 3 seeds (higher is better)",
    labels: ["Weather-only alert", "Twin nowcast", "Twin forecast", "Nowcast + personal", "Forecast + personal", "Oracle ceiling"],
    values: [0.53, 0.74, 0.69, 0.83, 0.80, 0.97],
    colors: [C.muted, C.blue, C.blue, C.heat, C.heat, C.line],
  });
  card(s, 7.0, 1.5, 2.5, 3.5);
  text(s, [
    { text: "+0.11", options: { fontFace: HEAD, fontSize: 30, bold: true, color: C.heat, breakLine: true } },
    { text: "AUROC gain from learning each worker, consistent on every seed", options: { fontSize: 12, breakLine: true } },
    { text: " ", options: { fontSize: 8, breakLine: true } },
    { text: "31%", options: { fontFace: HEAD, fontSize: 30, bold: true, color: C.blue, breakLine: true } },
    { text: "of danger episodes warned ≥ 30 min ahead (weather-only alert: 0%)", options: { fontSize: 12 } },
  ], { x: 7.2, y: 1.7, w: 2.15, h: 3.2, valign: "top" });
  s.addNotes("The ML forecaster (0.69) sits just below the nowcast (0.74) — honestly, not much gain from the classifier alone. The real lift is per-person bias correction (+0.11 AUROC). But the ML model's value is lead time: it warns 31% of episodes 30+ minutes in advance, versus 21% for the nowcast. That extra 10 minutes is time to seek shade before reaching 38 °C.");

  // 9. Dashboard
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "The clinician's live twin", "Real 28 May 2024 Delhi replay: patients ranked by risk, estimate with an 80% interval sized from real-data error");
  s.addImage({ path: path.join(IMG, "dashboard-twin.png"), x: 0.9, y: 1.45, w: 6.0, h: 3.75 });
  text(s, [
    { text: "Two numbers, never contradictory:", options: { bold: true, breakLine: true } },
    { text: "chance ≥ 38 °C now, and forecast within 60 min", options: { breakLine: true } },
    { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "Medication chips", options: { bold: true, breakLine: true } },
    { text: "β-blockers highlighted: their wearable readings are corrected", options: { breakLine: true } },
    { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "Validation toggle", options: { bold: true, breakLine: true } },
    { text: "overlay simulated true core temperature" },
  ], { x: 7.5, y: 1.5, w: 2.0, h: 3.8, fontSize: 11.5, valign: "top" });
  s.addNotes("Show Farhan Ali, a farm labourer on a beta-blocker. The band is honest uncertainty from real-data error, not the filter's overconfident variance.");

  // 10. What-if + review
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "From prediction to action", "What-if rest breaks for today; a medication review before summer");
  text(s, "What if Farhan rests 30 min in the shade at 14:30?", { x: 0.5, y: 1.45, w: 4.3, h: 0.35, fontSize: 13, bold: true });
  s.addImage({ path: path.join(IMG, "dashboard-whatif.png"), x: 0.5, y: 1.85, w: 4.3, h: 0.94 });
  text(s, "True minutes ≥ 38 °C fall from 39 to 16; alert minutes from 207 to 141.", { x: 0.5, y: 2.9, w: 4.3, h: 0.5, fontSize: 12, color: C.green });
  text(s, "Pre-summer review ranks patients with cited rules: triple-whammy kidney risk (BMJ 2013), falling eGFR (KDIGO 2024), β-blocker masking, heat-illness drugs (2026 cohort) and predicted heat strain.", {
    x: 0.5, y: 3.5, w: 4.3, h: 1.4, fontSize: 12, valign: "top",
  });
  s.addImage({ path: path.join(IMG, "dashboard-review.png"), x: 5.1, y: 1.45, w: 4.4, h: 2.75 });
  text(s, "Printable list for the PHC doctor · suggestions for clinician review, not orders", { x: 5.1, y: 4.3, w: 4.4, h: 0.4, fontSize: 10.5, color: C.muted, italic: true });
  s.addNotes("The twin doesn't just alarm. It re-simulates a rest break, and before the season it gives the doctor a ranked, evidence-cited medication review.");

  // 11. Why different
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "What makes ThermoTwin different", "Compared with a typical risk-score prototype");
  const diff = [
    [{ text: "", options: {} }, { text: "Typical prototype", options: { bold: true } }, { text: "ThermoTwin", options: { bold: true, color: C.heat } }],
    ["Role of the EHR", "Extra model features", "Changes the physiology model"],
    ["What “twin” means", "Classifier + dashboard", "Kalman filter + physics + personal learning"],
    ["Validation", "Synthetic only", "Real heat trials, held-out participants"],
    ["Honesty", "Single accuracy number", "Baselines, oracle ceiling, 3 seeds, negative results"],
    ["Action", "“Risk is high”", "What-if rest breaks + medication review"],
    ["India fit", "Generic", "Real Delhi heatwave, PHC workflow, outdoor workers"],
  ];
  s.addTable(diff, {
    x: 0.5, y: 1.45, w: 9, colW: [2.2, 2.9, 3.9], fontFace: BODY, fontSize: 12.5, color: C.ink,
    border: { type: "solid", pt: 0.75, color: C.line }, rowH: 0.47, valign: "middle",
  });
  s.addNotes("Keep this short: the record changes the physics, it is validated on real data, and every result is reported against baselines.");

  // 12. Limitations
  s = pres.addSlide();
  s.background = { color: C.white };
  title(s, "What we have not proven yet", "Stated plainly, with the next step for each");
  const lim = [
    ["Simulated patients", "Only the weather and validation data are real.", "Pilot with a PHC hypertension clinic under ethics approval"],
    ["Drug effect simulated", "PROSPIE volunteers were healthy; the β-blocker response was applied to their heart rate.", "Validate on real β-blocker users"],
    ["Gap to the oracle", "Forecast AUROC 0.80 vs 0.97 if current core were known.", "Better per-person heart-rate models"],
    ["False alarms", "Personal learning raises detection but also alerts.", "Calibrate thresholds with clinicians"],
  ];
  lim.forEach(([h, b, next], i) => {
    const y = 1.5 + i * 0.85;
    card(s, 0.5, y, 9, 0.72, i % 2 ? C.white : C.soft);
    text(s, h, { x: 0.7, y, w: 2.2, h: 0.72, fontSize: 13.5, bold: true, valign: "middle" });
    text(s, b, { x: 2.9, y, w: 3.7, h: 0.72, fontSize: 11.5, valign: "middle" });
    text(s, "→ " + next, { x: 6.7, y, w: 2.7, h: 0.72, fontSize: 11.5, color: C.green, valign: "middle" });
  });
  s.addNotes("Judges will ask these questions, so we answer them first. Research prototype, not a medical device.");

  // 13. Close
  s = pres.addSlide();
  s.background = { color: C.dark };
  text(s, "ThermoTwin", { x: 0.6, y: 1.2, w: 8.8, h: 0.9, fontFace: HEAD, fontSize: 44, bold: true, color: C.white });
  text(s, "The patient's record should change how we read their body in the heat.", { x: 0.6, y: 2.15, w: 8.6, h: 0.9, fontSize: 20, color: "D8D4CC" });
  text(s, [
    { text: "Run it: docker compose up --build  →  http://localhost:8080", options: { breakLine: true } },
    { text: "Code, results and evaluation reports: GitHub repository (MIT licence)" },
  ], { x: 0.6, y: 3.5, w: 8.8, h: 0.7, fontSize: 13, color: "E0774A" });
  text(s, "Research prototype on simulated patients and real weather. Not a medical device.", { x: 0.6, y: 4.8, w: 8.8, h: 0.3, fontSize: 10.5, color: "A19C92" });
  s.addNotes("Close on the one idea: the medical record should change how we read the body in the heat. Invite judges to run it with one command.");

  return pres.writeFile({ fileName: path.join(OUT, "ThermoTwin_presentation.pptx") });
}

buildArchitecture().then(buildDeck).then(() => console.log("wrote decks"));
