"""CYBERPULSE AI — inference & explainability service.

Loads the trained artifact and produces:
  - probability of suspicious withdrawal activity for an (ATM, window)
  - risk score 0-100 (combined with anomaly + graph + temporal signals)
  - SHAP-based feature contributions ("WHY HERE? WHY NOW?")

Falls back to native XGBoost gain importance if SHAP is unavailable.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd

try:
    import shap
    _HAS_SHAP = True
except ImportError:
    _HAS_SHAP = False

from ..preprocessing.features import FEATURES

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")

# Human-readable labels for the explanation panel
FEATURE_LABELS = {
    "complaints_last_24h": "Recent complaint surge (24h)",
    "complaints_last_72h": "Complaint volume (72h)",
    "complaints_last_7d": "Complaint volume (7d)",
    "complaint_accel": "Complaint acceleration",
    "tx_last_24h": "Withdrawal activity (24h)",
    "tx_last_72h": "Withdrawal concentration (72h)",
    "tx_last_7d": "Withdrawal volume (7d)",
    "tx_accel": "Activity acceleration",
    "complaint_density_10km": "Spatial complaint proximity (10km)",
    "tx_density_10km": "Nearby withdrawal density (10km)",
    "dist_km_last_complaint": "Distance to last incident",
    "hotspot_freq_30d": "Historical hotspot recurrence (30d)",
    "nearby_atms_5km": "ATM cluster density (5km)",
    "avg_tx_amount_7d": "Average withdrawal amount (7d)",
    "tx_amount_std_7d": "Amount variance (7d)",
    "unique_accounts_7d": "Unique account concentration (7d)",
    "suspicious_ratio_7d": "Suspicious account ratio (7d)",
    "mule_inflow_72h": "Mule-account inflow (72h)",
    "entity_degree": "Network degree (graph)",
    "connected_accounts": "Connected accounts (graph)",
    "suspicious_neighbors": "Suspicious neighbors (graph)",
    "hour_of_day": "Time-of-day pattern",
    "day_of_week": "Day-of-week pattern",
    "is_weekend": "Weekend activity",
    "hist_hourly_tx": "Historical hourly activity",
    "hist_hourly_complaints": "Historical complaint pattern",
}


@dataclass
class PredictionResult:
    atm_id: str
    window_start: str
    window_end: str
    probability: float
    risk_score: int
    confidence: float
    threshold: float
    factors: list[dict] = field(default_factory=list)
    feature_values: dict = field(default_factory=dict)


class InferenceService:
    def __init__(self, artifact_dir: str | None = None, model_path: str | None = None,
                 risk_weights: dict | None = None, alert_threshold: float = 65.0,
                 boost_factor: float = 0.15):
        self.artifact_dir = artifact_dir or ARTIFACT_DIR
        self.model_path = model_path or os.path.join(self.artifact_dir, "model_v1.joblib")
        self.risk_weights = risk_weights or {
            "ml": 0.40, "anomaly": 0.20, "graph": 0.15,
            "temporal": 0.15, "history": 0.10,
        }
        self.boost_factor = boost_factor
        self.alert_threshold = alert_threshold
        self.model = None
        self.scaler = None
        self.threshold = 0.5
        self.features: list[str] = list(FEATURES)
        self._shap_explainer = None
        self._shap_ready = False
        self._loaded = False

    # ── loading ───────────────────────────────────────────────────────────
    def load(self) -> bool:
        if not os.path.exists(self.model_path):
            return False
        bundle = joblib.load(self.model_path)
        self.model = bundle["model"]
        self.features = bundle.get("features", list(FEATURES))
        self.threshold = bundle.get("threshold", 0.5)
        self.scaler = bundle.get("scaler")
        self._loaded = True
        if _HAS_SHAP:
            try:
                self._shap_explainer = shap.TreeExplainer(self.model)
                self._shap_ready = True
            except Exception:
                self._shap_ready = False
        return True

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load_registry(self) -> dict | None:
        p = os.path.join(self.artifact_dir, "model_registry.json")
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
        return None

    # ── prediction ────────────────────────────────────────────────────────
    def predict(self, feature_row: dict, anomaly_score: float = 0.0,
                graph_score: float = 0.0, temporal_score: float = 0.0,
                history_score: float = 0.0) -> PredictionResult:
        if not self._loaded:
            raise RuntimeError("Model not loaded")
        X = pd.DataFrame([{k: feature_row.get(k, 0.0) for k in self.features}])
        prob = float(self.model.predict_proba(X)[:, 1][0])
        prob = float(np.clip(prob, 0.0, 1.0))

        # risk score: ML probability is the anchor (calibrated model);
        # contextual signals act as a corroboration boost.
        w = self.risk_weights
        ctx_w = w["anomaly"] + w["graph"] + w["temporal"] + w["history"]
        context = (
            w["anomaly"] * float(np.clip(anomaly_score, 0, 1))
            + w["graph"] * float(np.clip(graph_score, 0, 1))
            + w["temporal"] * float(np.clip(temporal_score, 0, 1))
            + w["history"] * float(np.clip(history_score, 0, 1))
        ) / (ctx_w if ctx_w else 1.0)
        risk = prob + self.boost_factor * context
        risk_score = int(round(risk * 100))
        risk_score = max(0, min(100, risk_score))

        # confidence: model certainty (distance from 0.5) scaled, blended with data volume
        certainty = abs(prob - 0.5) * 2  # 0..1
        confidence = float(np.clip(0.5 + 0.5 * certainty, 0.0, 0.99))

        factors = self._explain(X)
        return PredictionResult(
            atm_id=str(feature_row.get("atm_id", "")),
            window_start=str(feature_row.get("window_start", "")),
            window_end=str(feature_row.get("window_end", "")),
            probability=prob,
            risk_score=risk_score,
            confidence=confidence,
            threshold=self.threshold,
            factors=factors,
            feature_values={k: float(feature_row.get(k, 0.0)) for k in self.features},
        )

    def _explain(self, X: pd.DataFrame) -> list[dict]:
        """Return top feature contributions, sorted by |impact|."""
        if self._shap_ready:
            try:
                sv = self._shap_explainer.shap_values(X)
                if isinstance(sv, list):  # binary classifier returns [neg, pos]
                    sv = sv[1] if len(sv) > 1 else sv[0]
                vals = np.asarray(sv)[0]
                pairs = sorted(zip(self.features, vals.tolist()), key=lambda x: -abs(x[1]))
                out = []
                for name, v in pairs[:8]:
                    out.append({
                        "feature": name,
                        "label": FEATURE_LABELS.get(name, name),
                        "impact": round(float(v), 4),
                        "direction": "increase" if v > 0 else "decrease",
                    })
                return out
            except Exception:
                pass
        # fallback: native gain importance (direction unknown → use feature value vs mean)
        imp = self.model.feature_importances_
        pairs = sorted(zip(self.features, imp.tolist()), key=lambda x: -x[1])
        out = []
        for name, v in pairs[:8]:
            out.append({
                "feature": name,
                "label": FEATURE_LABELS.get(name, name),
                "impact": round(float(v), 4),
                "direction": "increase",
            })
        return out

    def predict_batch(self, feature_rows: list[dict],
                    anomaly_scores: list[float] | None = None,
                    graph_scores: list[float] | None = None,
                    temporal_scores: list[float] | None = None,
                    history_scores: list[float] | None = None) -> list[PredictionResult]:
        """Vectorized prediction + SHAP for many rows (fast path for predict_all)."""
        if not self._loaded:
            raise RuntimeError("Model not loaded")
        n = len(feature_rows)
        if n == 0:
            return []
        X = pd.DataFrame([{k: r.get(k, 0.0) for k in self.features} for r in feature_rows])
        probs = self.model.predict_proba(X)[:, 1]
        if self._shap_ready:
            try:
                sv = self._shap_explainer.shap_values(X)
                if isinstance(sv, list):
                    sv = sv[1] if len(sv) > 1 else sv[0]
                shap_mat = np.asarray(sv)
            except Exception:
                shap_mat = None
        else:
            shap_mat = None

        w = self.risk_weights
        ctx_w = w["anomaly"] + w["graph"] + w["temporal"] + w["history"]
        out = []
        for i, r in enumerate(feature_rows):
            prob = float(np.clip(probs[i], 0.0, 1.0))
            an = float(np.clip((anomaly_scores or [0.0])[i], 0, 1))
            gs = float(np.clip((graph_scores or [0.0])[i], 0, 1))
            ts = float(np.clip((temporal_scores or [0.0])[i], 0, 1))
            hs = float(np.clip((history_scores or [0.0])[i], 0, 1))
            context = (w["anomaly"] * an + w["graph"] * gs + w["temporal"] * ts
                       + w["history"] * hs) / (ctx_w if ctx_w else 1.0)
            risk = prob + self.boost_factor * context
            risk_score = int(max(0, min(100, round(risk * 100))))
            certainty = abs(prob - 0.5) * 2
            confidence = float(np.clip(0.5 + 0.5 * certainty, 0.0, 0.99))

            if shap_mat is not None:
                vals = shap_mat[i]
                pairs = sorted(zip(self.features, vals.tolist()), key=lambda x: -abs(x[1]))
                factors = [
                    {"feature": name, "label": FEATURE_LABELS.get(name, name),
                     "impact": round(float(v), 4),
                     "direction": "increase" if v > 0 else "decrease"}
                    for name, v in pairs[:8]
                ]
            else:
                imp = self.model.feature_importances_
                pairs = sorted(zip(self.features, imp.tolist()), key=lambda x: -x[1])
                factors = [
                    {"feature": name, "label": FEATURE_LABELS.get(name, name),
                     "impact": round(float(v), 4), "direction": "increase"}
                    for name, v in pairs[:8]
                ]
            out.append(PredictionResult(
                atm_id=str(r.get("atm_id", "")),
                window_start=str(r.get("window_start", "")),
                window_end=str(r.get("window_end", "")),
                probability=prob,
                risk_score=risk_score,
                confidence=confidence,
                threshold=self.threshold,
                factors=factors,
                feature_values={k: float(r.get(k, 0.0)) for k in self.features},
            ))
        return out

    def feature_importance(self, top_n: int = 15) -> list[dict]:
        if not self._loaded:
            return []
        imp = self.model.feature_importances_
        pairs = sorted(zip(self.features, imp.tolist()), key=lambda x: -x[1])
        return [
            {"feature": f, "label": FEATURE_LABELS.get(f, f), "importance": round(float(v), 5)}
            for f, v in pairs[:top_n]
        ]

    def shap_summary_values(self, X: pd.DataFrame, max_display: int = 15) -> list[dict]:
        """Mean |SHAP| per feature over a sample — for the model performance page."""
        if self._shap_ready:
            try:
                sv = self._shap_explainer.shap_values(X)
                if isinstance(sv, list):
                    sv = sv[1] if len(sv) > 1 else sv[0]
                sv = np.asarray(sv)
                mean_abs = np.abs(sv).mean(axis=0)
                pairs = sorted(zip(self.features, mean_abs.tolist()), key=lambda x: -x[1])
                return [
                    {"feature": f, "label": FEATURE_LABELS.get(f, f), "mean_abs_shap": round(float(v), 5)}
                    for f, v in pairs[:max_display]
                ]
            except Exception:
                pass
        return self.feature_importance(max_display)


# ── module-level singleton helpers ─────────────────────────────────────────
_service: InferenceService | None = None


def get_service(artifact_dir: str | None = None, model_path: str | None = None,
                risk_weights: dict | None = None, alert_threshold: float = 65.0,
                boost_factor: float = 0.15) -> InferenceService:
    global _service
    if _service is None or (artifact_dir and _service.artifact_dir != artifact_dir):
        _service = InferenceService(artifact_dir, model_path, risk_weights, alert_threshold,
                                    boost_factor)
        _service.load()
    return _service


def reset_service():
    global _service
    _service = None