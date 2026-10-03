# ThermoTwin

**A medication-aware hypertension digital twin that predicts when India's heat will tip a patient into crisis.**

Built for the Happiest Health *Digital Twin Challenge 2026*.

> Research prototype on synthetic data. Not a medical device.

## Submission at a glance

| | |
|---|---|
| **Challenge** | Happiest Health Digital Twin Challenge 2026 |
| **Problem** | 315 million hypertensive Indians work outdoors; their BP medicines change how heat affects them |
| **Twin input** | Wearable heart rate + EHR medication list + real heatwave weather |
| **Key novelty** | Medication-aware ECTemp filter: corrects for beta-blocker HR blunting before estimating core temperature |
| **Real-data result** | 62% of danger minutes caught vs 18% for HR-only — validated on 22 participants, 99 real heat trials (PROSPIE) |
| **Stack** | Python · FastAPI · React 19 · Docker Compose |
| **Architecture** | [`docs/ThermoTwin_architecture.pdf`](docs/ThermoTwin_architecture.pdf) |
| **Presentation** | [`docs/ThermoTwin_presentation.pdf`](docs/ThermoTwin_presentation.pdf) |

## The idea in one paragraph

About 315 million Indian adults have hypertension, and millions of them work outdoors through
heatwaves. Their blood-pressure medicines change how their bodies handle heat. Beta-blockers
blunt the heart-rate rise that wearable heat models rely on, so those models under-read core
temperature for exactly these patients. ThermoTwin reads the patient's medication record and
corrects its physiology model before estimating and forecasting heat strain.

## Tech stack

| Layer | Technology |
|---|---|
| Physics model | ECTemp extended Kalman filter (Buller 2013) + Gagge two-node thermoregulation |
| Ground truth | JOS-3 multi-node thermoregulation (`pythermalcomfort`) |
| Forecaster | `HistGradientBoostingClassifier` (scikit-learn) |
| Real-data validation | PROSPIE dataset (22 participants, 99 trials, Loughborough, CC BY-NC 4.0) |
| Weather | Open-Meteo historical API — real Delhi heatwave May–June 2024 |
| Backend | FastAPI + Pydantic, `uv`, `ruff`, `pytest` |
| Frontend | React 19 + Vite + TypeScript + Recharts + TanStack Query + zod |
| Deployment | Docker Compose (non-root API + nginx dashboard) |
| CI | GitHub Actions (Python + dashboard jobs) |

## Run everything with Docker

```bash
docker compose up --build        # first build trains the forecaster (~5–10 min)
```

Open http://localhost:8080. The API runs as a non-root user with a health check. The
dashboard waits until the API is healthy, and nginx serves it and proxies `/api`. Set
`THERMOTWIN_PORT` to use a different host port.

## Quickstart (development)

```bash
uv sync
uv run pytest
uv run python -m thermotwin.ablation --patients 60
```

The ablation writes `reports/ablation_summary.csv` and `reports/ablation_beta_blocker.png`.

## Headline result: real heat-trial data (PROSPIE, 22 participants, 99 trials)

**1. ECTemp validation.** On real rectal temperature, our ECTemp gives RMSE **0.32 °C**, in line
with the published ~0.3 °C. Adding skin temperature barely helps (0.31 °C, participant-held-out
CV), so we don't claim it.

**2. Beta-blocker ablation on real data.** Real heart rate and core temperature, with a hidden
beta-blocker response applied to heart rate only:

| Estimator | RMSE | Bias | Danger minutes caught (≥38 °C) | False-alarm rate |
|---|---|---|---|---|
| ECTemp (HR only) | 0.63 °C | −0.48 °C | 18% | 0% |
| **ThermoTwin (medication-aware)** | **0.39 °C** | **−0.20 °C** | **62%** | **8%** |

Reproduce (the data is CC BY-NC 4.0 and not committed):

```bash
uv run python -m thermotwin.prospie --download
uv run python -m thermotwin.fusion
uv run python -m thermotwin.real_ablation
```

Alerts fire when the estimate's upper bound (mean + 1 SD) reaches 38 °C. PROSPIE
participants are healthy volunteers, so the drug effect is simulated. A trial with real
beta-blocker users would be the next validation step.

## 60-minute forecast (real Delhi heatwave weather, May–June 2024)

Question at each minute: *will core temperature reach 38 °C in the next 60 minutes?*
There are 200 simulated workers, each on a real Delhi heatwave day (Open-Meteo, peaks of 46 °C).
We test on 60 patients the model never trained on.

Mean over 3 seeds (11, 42, 123), 200 patients each, tested on unseen patients:

| Method | AUROC (range) | Episodes warned ≥30 min ahead |
|---|---|---|
| Weather-only heat alert | 0.53 (0.47–0.59) | 0% |
| Twin nowcast (no ML) | 0.74 (0.69–0.78) | 21% |
| ThermoTwin 60-min forecast | 0.69 (0.57–0.75) | 28% |
| Twin nowcast + learned personal bias | **0.83** (0.77–0.90) | 25% |
| **ThermoTwin forecast + learned personal bias** | **0.80** (0.69–0.88) | **31%** |
| Oracle ceiling (knows true current core) | 0.97 (0.97–0.98) | 60% |

**Honest reading:**
- The twin beats a city-wide weather alert.
- The oracle shows the bottleneck is *estimating current core temperature*, not forecasting.
  On heatwave days workers hover near 37.8 °C (SD 0.23 °C), so the twin's ~0.25 °C
  estimation error is as large as the whole spread.
- Things we tried that did not help:
  - a Gagge physics projection
  - anchoring the start with a thermometer reading
  - thermometer spot readings at each break
- **Per-person learning (real data).** The twin learns each worker's bias from a few
  thermometer readings (±0.3 °C) on *earlier* shifts, then corrects new shifts without any
  reading on the day. Tested on PROSPIE, learning only from a participant's other trials:

  | Scenario | Error before → after | Danger caught | False alarms |
  |---|---|---|---|
  | No drug | 0.355 → **0.336 °C** | 84% → 85% | 33% → 38% |
  | Beta-blocker | 0.438 → **0.365 °C** (bias −0.25 → −0.05) | 59% → **79%** | 13% → 38% |

  A linear "rest + activity + heat" heart-rate model was also tried and rejected
  (0.49–0.98 °C vs 0.36 °C).

**Honest reading of the table:** the main AUROC gain (0.69 → 0.80) comes from per-person bias
correction, not from the ML forecaster itself (which actually sits below the nowcast at 0.69 vs 0.74).
The ML model's practical value is *lead time*: it warns 31% of episodes ≥30 minutes ahead vs 21%
for the nowcast, giving workers time to seek shade before they reach danger.

```bash
uv run python -m thermotwin.forecast --patients 200                  # population twin
uv run python -m thermotwin.forecast --patients 200 --learn-personal # with per-person learning
```

## Clinician dashboard

The dashboard replays the real Delhi heatwave of 28 May 2024 (45.8 °C) for 12 simulated
hypertensive outdoor workers. For each worker it shows:
- the medication-aware core estimate with an 80% interval, sized from error measured on real
  heat trials
- two separate numbers: the chance core is ≥38 °C *now*, and the ML forecast for the *next
  60 minutes*
- medication heat-risk notes
- a what-if simulator that re-runs the shift with an extra rest break
- a **pre-summer review** tab: a printable, ranked list of findings for the clinician. Each
  finding comes from a transparent rule and cites its evidence:
  - diuretic + ACE inhibitor/ARB + NSAID "triple whammy" (Lapi et al., BMJ 2013)
  - eGFR falling ≥ 5 mL/min/1.73 m² a year or below 60 (KDIGO 2024)
  - beta-blockers masking heat strain in heart rate (ThermoTwin real-data ablation)
  - ACE inhibitor/ARB/calcium-channel blocker/thiazide diuretic heat-illness risk (2026 cohort study)
  - heat strain predicted by the twin's heatwave replay (NDMA guidance)

```bash
uv run python -m thermotwin.forecast --patients 200 --seed 7 --save-model   # once, ~5 min
uv run uvicorn thermotwin.api.main:app --port 8010                          # API
npm --prefix dashboard install && npm --prefix dashboard run dev            # http://localhost:5173
```

The patient-list colour uses the higher of "now" and "60-min forecast" as a cautious
triage rule. That rule itself has not been separately evaluated.

## Simulated cohort (60 patients, seed 42)

| Group | Estimator | Core-temp RMSE | Bias | Danger missed | False-alarm minutes |
|---|---|---|---|---|---|
| No beta-blocker | ECTemp / ThermoTwin (identical) | 0.18 °C | +0.01 °C | 6% | 2,576 |
| On beta-blocker | ECTemp (HR only) | 0.52 °C | −0.52 °C | 95% | 0 |
| On beta-blocker | **ThermoTwin** | **0.23 °C** | **−0.04 °C** | **15%** | 3,285 |

The simulator is easier than reality (0.18 °C vs 0.32 °C on real data), so treat the real-data
results above as the headline numbers.

![Ablation](reports/ablation_beta_blocker.png)

### How the evaluation avoids circularity

- **Ground truth** core and skin temperature come from **JOS-3**, a multi-node
  thermoregulation model (`pythermalcomfort`).
- **Heart rate** is generated by a separate linear model, not ECTemp's quadratic.
- **Each patient's true beta-blocker response is hidden**. The twin only sees the EHR
  medication list and uses population priors.
- The simulated cohort is a sanity check. The real-data PROSPIE results above are the
  primary evidence.

## How it works (so far)

| Module | Role |
|---|---|
| `ectemp.py` | ECTemp extended Kalman filter: core temperature from 1-minute heart rate (Buller et al. 2013) |
| `medication.py` | Drug classes; beta-blocker correction (un-blunt HR with population priors, widen noise) |
| `cohort.py` | Synthetic hypertensive outdoor workers: EHR-visible fields plus hidden physiology |
| `simulator.py` | Minute-by-minute shift: JOS-3 thermoregulation + separate HR model + heatwave day |
| `ablation.py` | Signature comparison on the simulated cohort |
| `prospie.py` | Loader for the real PROSPIE heat-trial dataset |
| `fusion.py` | Participant-held-out ECTemp validation and skin-temperature fusion test |
| `weather.py` | Open-Meteo historical weather (cached), Delhi heatwave 2024 |
| `forecast.py` | 60-minute danger forecast, baselines, oracle ceiling, lead times |
| `personal.py` | Per-person bias learned from earlier shifts' thermometer readings |
| `personal_validation.py` | Real-data test of per-person learning (leave-own-trial-out) |
| `review.py` | Evidence-referenced pre-summer medication and heat review rules |
| `api/` | FastAPI service: patients, timelines, what-if, review |
| `real_ablation.py` | Beta-blocker ablation on real heart rate and core temperature |

## Known limitations

- **Beta-blocker drug effect is simulated.** The PROSPIE participants were healthy volunteers; no real beta-blocker users were in the dataset. The 62% vs 18% headline uses a simulated blunting drawn from the same population priors the twin corrects — result is optimistic by construction. A prospective trial with real beta-blocker users is the next validation step.
- **Diabetes not modelled.** ~40% of hypertensive Indians have co-morbid diabetes. Sulfonylureas cause hypoglycaemia (impairs thermoregulation); metformin requires caution with dehydration (AKI risk). Not included in the current drug model.
- **Beta-blocker class not differentiated.** Cardioselective agents (atenolol, metoprolol — dominant in India) blunt exercise HR less than non-selective (propranolol). A drug-specific prior table would improve correction accuracy.
- **Cohort is synthetic.** All patients are generated from statistical distributions, not from a real EHR dataset.
- **Not a medical device.** Priority scores are unvalidated triage heuristics.

## Roadmap

- [x] Core-temperature filter, medication correction, ground-truth simulator, ablation
- [ ] Reduce false alarms; no-wearable Tier 0 model (skin fusion tested: negligible gain)
- [x] Real-data validation and beta-blocker ablation on PROSPIE
- [ ] Synthea cohort with a custom beta-blocker module, exported as FHIR
- [x] Real heatwave replay from Open-Meteo historical weather
- [x] 60-minute forecast with baselines and oracle ceiling
- [x] Per-person bias learning across shifts (validated on real data)
- [ ] Conformal intervals; reduce false alarms
- [x] Kidney-injury (triple-whammy) warning and pre-summer medication review
- [ ] Acclimatisation tracking
- [x] FastAPI service and React clinician dashboard with a what-if simulator
- [x] Docker Compose (API + dashboard)
- [x] Architecture diagram and presentation (`docs/`)
- [ ] Demo video

## Submission details

- **Team:** _TBD_
- **College / incubator:** _TBD_
- **Video:** _TBD_
- **Architecture diagram:** [`docs/ThermoTwin_architecture.pdf`](docs/ThermoTwin_architecture.pdf) (editable `.pptx` alongside)
- **Presentation:** [`docs/ThermoTwin_presentation.pdf`](docs/ThermoTwin_presentation.pdf) (editable `.pptx` with speaker notes)
- **License:** MIT (see `LICENSE`)

## Rebuilding the slides

```bash
npm install --prefix /tmp/deck pptxgenjs
NODE_PATH=/tmp/deck/node_modules node docs/build_slides.js   # writes docs/*.pptx
```

Export the PDFs from PowerPoint or Keynote. Dashboard screenshots live in `docs/img/`.

## References

- Buller MJ et al. Estimation of human core temperature from sequential heart rate observations. *Physiol Meas* 2013;34(7):781–798.
- Takahashi Y et al. Thermoregulation model JOS-3 with new open source code. *Energy and Buildings* 2021;231:110575.
- Antihypertensive medication and heat-related illness during heatwaves (2026). doi:10.1002/pds.70447
