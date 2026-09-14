---
title: "CYBERPULSE AI: Cybercrime Intelligence Command Center for Proactive ATM Cash‑Out Threat Prediction"
tags:
  - Python
  - FastAPI
  - React
  - XGBoost
  - SHAP
  - anomaly detection
  - graph analytics
  - fraud detection
authors:
  - name: "Vetrivel Ravichandiran"
    orcid: "0009-0000-9447-0529"
affiliations:
  - name: "Independent"
    index: 1
date: "2026-09-15"
bibliography: paper.bib
---

# Summary

ATM cash‑out fraud often unfolds in rapid bursts: a fraud ring can move from reconnaissance to mule-account staging and coordinated withdrawals within hours, leaving reactive monitoring and manual triage one step behind. **CYBERPULSE AI** is an open-source prototype “cybercrime intelligence command center” that predicts *where* and *when* suspicious ATM withdrawal activity is likely to occur in the *next operational window* and supports a complete workflow from **alert → investigation → PDF report**.

CYBERPULSE AI combines an XGBoost-based risk model with **graph analytics** and **anomaly detection**, then explains high-risk predictions using **SHAP** so analysts can understand and justify actions. The system exposes a FastAPI backend for prediction, alerting, and investigation management, and a React-based frontend for hotspot mapping and drill-down analytics. While the current release is validated using **synthetic data only**, the architecture is designed to support real deployments with governed data sources and auditable case workflows.

# Statement of need

Fraud monitoring systems commonly rely on rule-based triggers or retrospective anomaly flags that detect suspicious behavior after losses occur. In practice, investigative and banking fraud-cell workflows require (i) *proactive* prioritization, (ii) transparent explanations to support escalation and coordination, and (iii) structured case management for evidence collection and reporting. Existing research prototypes frequently stop at model training and evaluation, leaving a gap between predictive modeling and operational use.

CYBERPULSE AI addresses this gap by providing:

1. **Near-term threat prediction** at the granularity of *(ATM, time window)* to support proactive staffing and intervention.
2. **Model explainability** using SHAP to produce human-readable drivers for each prediction.
3. **Entity linking and graph context** to connect accounts, ATMs, complaints, and behaviors into an investigative view.
4. **Operational workflows** including alert lifecycle management, investigations, timelines, and exportable PDF reports.
5. **Reproducible demo environment** with deterministic synthetic data generation and end-to-end verification scripts.

This combination makes CYBERPULSE AI suitable for software-focused dissemination, reproducible evaluation, and extension by researchers and practitioners working on financial fraud prevention, cybercrime intelligence, and decision-support systems.

# Functionality and design

## Core prediction unit and features

The system predicts risk for each ATM over a fixed forward-looking window (default: **6 hours**) using a point-in-time feature pipeline. A shared `FeatureContext` computes features for both training and live inference to avoid train/serve skew. The model target is whether an ATM will experience **≥3 withdrawals in the next window**, with 27 engineered features spanning temporal activity patterns, spatial signals, transaction intensity, anomaly indicators, and network/graph-derived signals.

## Risk engine and explainability

CYBERPULSE AI anchors on an XGBoost classifier and produces a **0–100 risk score**. The score combines the model probability with configurable “boost” components derived from anomaly, graph, temporal, and historical signals. For interpretability, the system computes **SHAP** explanations for predictions, surfacing the strongest drivers of risk to guide analyst judgment and downstream action.

## Operational workflows

- **Predictions:** Batch generation for the next window over all active ATMs, executed in the background and streamed to the UI via WebSocket events.
- **Alerts:** Auto-created when risk exceeds a configurable threshold; supports acknowledge/escalate/resolve and investigation creation.
- **Investigations:** Case management with notes, status transitions, timeline reconstruction, linked entities, and **PDF report** generation.
- **Visualization:** Live hotspot map with layer toggles and drill-down into ATM-level risk and explanation details.

# Implementation

CYBERPULSE AI includes:

- **Backend:** FastAPI services for authentication, dashboards, predictions, alerts, investigations, graph and map endpoints, simulation, realtime updates (WebSockets), and report generation.
- **Frontend:** React + Vite command-center UI with Leaflet for mapping and Recharts for analytics.
- **ML tooling:** synthetic data generator, feature pipeline, training, inference, SHAP explainability, and saved evaluation artifacts.
- **Scripts:** dataset generation, model training, database seeding, demo setup, and API verification.

# Limitations

This release is a **prototype validated on synthetic data only**. The synthetic environment is intended for reproducibility and demonstration of the full end-to-end workflow, not for claiming real-world operational performance. Production usage would require (i) governed ingestion of real transaction and complaint data, (ii) careful privacy and compliance controls, (iii) calibration of alert thresholds to operational constraints, and (iv) ongoing monitoring for drift and adversarial adaptation.

# Availability

- **Source code:** `TODO (GitHub URL)`
- **Documentation:** `TODO`
- **License:** `TODO (e.g., MIT/Apache-2.0/GPL-3.0)`
- **Platforms:** Python (backend + ML), Node.js (frontend)

# Acknowledgements

The author thanks the open-source communities behind XGBoost, SHAP, FastAPI, React, Leaflet, and related tooling that enabled rapid prototyping of the system.

# References
