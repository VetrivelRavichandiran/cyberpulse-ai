# CYBERPULSE AI — Cybercrime Intelligence Command Center

Proactive **cash-withdrawal threat prediction** for I4C & banking fraud cells.
An ML + graph + anomaly fusion engine that predicts *where* and *when*
suspicious ATM cash-out activity is likely, explains *why* (SHAP), and drives a
full investigation workflow (alerts → cases → PDF reports).

> **Disclaimer:** Prototype validated on **synthetic data** only. All entities,
> transactions and complaints are generated — no real persons, banks or
> institutions are represented.

---

## Quick start (5 minutes)

```bash
# 1. Install dependencies
make setup                # python (ml + backend) + npm (frontend)

# 2. Build the demo environment (data → train → seed).
#    A pre-trained model + seeded DB are already included, so this step is
#    optional — run it only if you want to regenerate everything from scratch.
make demo

# 3. Run the backend (API on :8000)
make run-backend

# 4. In a second terminal, run the frontend (dev server on :5173)
make run-frontend

# 5. Open http://localhost:5173 and sign in
#    admin / Admin@123
```

Smoke-test a running backend:

```bash
make verify               # 18 endpoint checks, prints pass/fail
```

---

## Demo accounts

| Username | Role | Password |
|---|---|---|
| `admin` | ADMIN | `Admin@123` |
| `analyst` | I4C_ANALYST | `Analyst@123` |
| `state_officer` | STATE_OFFICER | `State@123` |
| `district_officer` | DISTRICT_OFFICER | `District@123` |
| `investigator` | INVESTIGATOR | `Invest@123` |
| `bank_user` | BANK_USER | `Bank@123` |

---

## What's inside

```
backend/    FastAPI app — auth, dashboard, predictions, alerts, investigations,
            map, graph, model, simulation, demo, realtime (WebSocket), reports
frontend/   React + Vite + Leaflet + Recharts command-center UI
ml/         Data generator, feature pipeline, training, inference + SHAP,
            artifacts (pre-trained model_v1, anomaly detector, registry)
scripts/    generate_dataset / train_model / seed_database / setup_demo / verify_api
data/       raw synthetic CSVs, processed prediction units, demo SQLite DB
```

### Feature pipeline (no train/serve skew)
A single `FeatureContext` (`ml/preprocessing/features.py`) computes
point-in-time features for every (ATM, 6-hour window) and is used by **both**
training and live inference. 27 features across temporal, spatial, financial
and network signals. Target: ≥3 withdrawals in the next 6h window.

### Risk engine
`risk = ML probability (anchor) + boost × (anomaly + graph + temporal + history)`
— weights configurable in `.env`. Output: 0–100 risk score, band, SHAP
explanation and a recommended action.

### Model performance (saved evaluation, not hard-coded)
XGBoost classifier, test AUC ≈ 0.96 (see `/model/info` and
`ml/artifacts/evaluation_v1.json`). Baseline logistic regression included for
comparison.

---

## Key workflows

- **Predictions** — "Generate for next window" runs the real model over all
  active ATMs in the background and streams the result over WebSocket
  (`predictions_generated` event). Re-running for the same window is
  idempotent (no duplicate rows/alerts).
- **Alerts** — auto-created when risk ≥ threshold. Acknowledge / escalate /
  resolve, or open an investigation directly.
- **Investigations** — case management with status transitions, notes,
  timeline, linked entity graph, and a downloadable **PDF report**.
- **Live Map** — hotspots, risk zones, complaints, ATMs, withdrawals with
  layer toggles and click-through detail (risk, probability, SHAP drivers).
- **Model & AI** — live metrics, feature importance, SHAP summary.
- **Demo Scenario** — replays a controlled fraud-ring lifecycle end-to-end
  (complaint surge → mule inflow → recon → cash-out burst) with a live event
  stream; reset anytime.
- **Simulation** — what-if: change complaint volume / transaction intensity /
  radius and compare current vs simulated risk.

---

## Configuration

Copy `.env.example` → `.env`. Key settings:

- `DATABASE_URL` — SQLite by default (`data/demo/cyberpulse.db`); PostgreSQL
  supported for production.
- `RISK_BOOST_FACTOR`, `RISK_WEIGHT_*`, `RISK_ALERT_THRESHOLD` — risk engine.
- `JWT_SECRET`, `JWT_EXPIRE_MINUTES` — auth.
- `NEO4J_URI`, `REDIS_URL` — optional; the app degrades gracefully to the
  PostgreSQL/SQLite graph and an in-process realtime hub when absent.

---

## Notes

- The demo SQLite database lives on disk; on networked filesystems the batch
  prediction write is I/O-bound, which is why generation runs in the
  background and reports via WebSocket.
- Map tiles use key-free OpenStreetMap (dark-styled via CSS filter).
- `make demo` regenerates data + retrains + reseeds (deterministic seed 42).