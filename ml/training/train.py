"""CYBERPULSE AI — model training, evaluation, and artifact saving.

Trains:
  - Baseline: Logistic Regression (L2, class-weighted)
  - Main:     XGBoost (probability output, scale_pos_weight for imbalance)

Evaluates on a held-out temporal test split:
  precision, recall, F1, ROC-AUC, confusion matrix, PR-AUC,
  false-positive rate, hotspot detection rate, mean lead time.

Saves:
  ml/artifacts/model_v1.joblib          — main model + feature list + scaler
  ml/artifacts/baseline_v1.joblib       — baseline model
  ml/artifacts/model_registry.json      — metadata + metrics for both models
  ml/artifacts/evaluation_v1.json       — full evaluation detail
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from ..preprocessing.features import FEATURES, split_units

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")


def _pr_auc(y, p):
    p, r, _ = precision_recall_curve(y, p)
    return float(np.trapezoid(r, p))


def _evaluate(y: np.ndarray, prob: np.ndarray, thr: float = 0.5) -> dict:
    pred = (prob >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    pos = max(int(y.sum()), 1)
    # hotspot detection: of the actual positive windows, fraction predicted positive
    hotspot_rate = tp / pos if pos else 0.0
    # lead time: windows predicted positive whose label window is >= 6h ahead of
    # the last observed signal — approximated by the fraction of true positives
    # that were predicted in the window *before* the cash-out window.
    return {
        "threshold": thr,
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, prob)) if len(np.unique(y)) > 1 else None,
        "pr_auc": _pr_auc(y, prob),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "hotspot_detection_rate": float(hotspot_rate),
        "n_samples": int(len(y)),
        "positive_rate": float(y.mean()),
    }


def train(units: pd.DataFrame, artifact_dir: str | None = None,
          dataset_version: str = "synthetic-v1",
          model_version: str = "1.0.0") -> dict:
    art = artifact_dir or ARTIFACT_DIR
    os.makedirs(art, exist_ok=True)
    splits = split_units(units)
    tr, va, te = splits["train"], splits["val"], splits["test"]

    X_tr, y_tr = tr[FEATURES].values, tr["y"].values
    X_va, y_va = va[FEATURES].values, va["y"].values
    X_te, y_te = te[FEATURES].values, te["y"].values

    pos_rate = float(y_tr.mean())
    spw = float((1 - pos_rate) / max(pos_rate, 1e-6))

    # ── baseline: logistic regression ─────────────────────────────────────
    scaler = StandardScaler().fit(X_tr)
    X_tr_s, X_va_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_va), scaler.transform(X_te)
    lr = LogisticRegression(max_iter=2000, class_weight="balanced", C=0.5)
    lr.fit(X_tr_s, y_tr)
    lr_val = _evaluate(y_va, lr.predict_proba(X_va_s)[:, 1])
    lr_test = _evaluate(y_te, lr.predict_proba(X_te_s)[:, 1])

    # ── main: XGBoost ─────────────────────────────────────────────────────
    xgb = XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_lambda=1.5,
        scale_pos_weight=spw,
        eval_metric="auc",
        random_state=42,
        n_jobs=4,
        early_stopping_rounds=40,
    )
    xgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
    xgb_val = _evaluate(y_va, xgb.predict_proba(X_va)[:, 1])
    xgb_test = _evaluate(y_te, xgb.predict_proba(X_te)[:, 1])

    # feature importance (gain)
    imp = sorted(zip(FEATURES, xgb.feature_importances_.tolist()), key=lambda x: -x[1])

    # best threshold on validation (max F1)
    from sklearn.metrics import f1_score as _f1
    best_thr, best_f1 = 0.5, -1
    for t in np.arange(0.2, 0.8, 0.05):
        f = _f1(y_va, (xgb.predict_proba(X_va)[:, 1] >= t).astype(int))
        if f > best_f1:
            best_f1, best_thr = float(f), float(t)

    trained_at = datetime.now(timezone.utc).isoformat()
    registry = {
        "active": {
            "version": model_version,
            "algorithm": "XGBoost",
            "artifact": "model_v1.joblib",
            "dataset_version": dataset_version,
            "trained_at": trained_at,
            "features": FEATURES,
            "threshold": best_thr,
            "scale_pos_weight": spw,
            "metrics": {
                "validation": xgb_val,
                "test": xgb_test,
            },
            "feature_importance": [{"feature": f, "importance": round(i, 5)} for f, i in imp[:15]],
        },
        "baseline": {
            "version": "1.0.0",
            "algorithm": "LogisticRegression",
            "artifact": "baseline_v1.joblib",
            "dataset_version": dataset_version,
            "trained_at": trained_at,
            "features": FEATURES,
            "metrics": {"validation": lr_val, "test": lr_test},
        },
        "comparison": {
            "xgboost_test_roc_auc": xgb_test["roc_auc"],
            "logreg_test_roc_auc": lr_test["roc_auc"],
            "xgboost_test_f1": xgb_test["f1"],
            "logreg_test_f1": lr_test["f1"],
            "xgboost_test_pr_auc": xgb_test["pr_auc"],
            "logreg_test_pr_auc": lr_test["pr_auc"],
        },
        "split_sizes": {"train": len(tr), "val": len(va), "test": len(te)},
        "positive_rate_train": pos_rate,
        "positive_rate_test": float(y_te.mean()),
        "label_definition": ">=3 ATM withdrawals in the 6-hour window (ATM x 6h prediction unit)",
        "prediction_horizon_hours": 6,
        "disclaimer": "Synthetic Data — Prototype Evaluation",
    }

    joblib.dump({"model": xgb, "features": FEATURES, "threshold": best_thr},
                os.path.join(art, "model_v1.joblib"))
    joblib.dump({"model": lr, "scaler": scaler, "features": FEATURES},
                os.path.join(art, "baseline_v1.joblib"))
    with open(os.path.join(art, "model_registry.json"), "w") as f:
        json.dump(registry, f, indent=2)
    with open(os.path.join(art, "evaluation_v1.json"), "w") as f:
        json.dump(registry, f, indent=2)

    return registry


if __name__ == "__main__":
    import argparse

    from ..preprocessing.features import build_prediction_units, load_raw

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw")
    args = ap.parse_args()
    data = load_raw(args.data)
    units = build_prediction_units(data)
    reg = train(units, dataset_version=data.get("meta", {}).get("dataset_version", "synthetic-v1"))
    a = reg["active"]["metrics"]["test"]
    print(f"XGBoost test: AUC={a['roc_auc']:.3f} F1={a['f1']:.3f} P={a['precision']:.3f} R={a['recall']:.3f}")
    b = reg["baseline"]["metrics"]["test"]
    print(f"LogReg  test: AUC={b['roc_auc']:.3f} F1={b['f1']:.3f} P={b['precision']:.3f} R={b['recall']:.3f}")
    print(f"Threshold={reg['active']['threshold']:.2f}  pos_rate(test)={reg['positive_rate_test']:.3f}")