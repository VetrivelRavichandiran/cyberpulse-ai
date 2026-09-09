"""CYBERPULSE AI — model registry / performance router.

All metrics come from the real saved evaluation artifacts — never hard-coded.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..config import get_settings
from ..database import get_db
from ml.inference.service import get_service

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/info")
def info(_user=Depends(get_current_user)):
    s = get_settings()
    svc = get_service()
    reg = svc.load_registry()
    if reg is None:
        raise HTTPException(503, "Model registry not found — run scripts/train_model.py")
    active = reg["active"]
    return {
        "version": active["version"],
        "algorithm": active["algorithm"],
        "dataset_version": active["dataset_version"],
        "trained_at": active["trained_at"],
        "threshold": active["threshold"],
        "features": active["features"],
        "split_sizes": reg["split_sizes"],
        "positive_rate_test": reg["positive_rate_test"],
        "label_definition": reg["label_definition"],
        "prediction_horizon_hours": reg["prediction_horizon_hours"],
        "disclaimer": reg["disclaimer"],
        "metrics": active["metrics"],
        "comparison": reg["comparison"],
        "feature_importance": active["feature_importance"],
        "model_loaded": svc.loaded,
        "shap_available": svc._shap_ready,
    }


@router.get("/feature-importance")
def feature_importance(top_n: int = 15, _user=Depends(get_current_user)):
    svc = get_service()
    if not svc.loaded:
        raise HTTPException(503, "Model not loaded")
    return svc.feature_importance(top_n)


@router.get("/shap-summary")
def shap_summary(_user=Depends(get_current_user)):
    """Mean |SHAP| per feature over a real sample of prediction units."""
    svc = get_service()
    if not svc.loaded:
        raise HTTPException(503, "Model not loaded")
    s = get_settings()
    units_path = os.path.join(s.data_dir_resolved, "processed", "prediction_units.csv")
    if not os.path.exists(units_path):
        raise HTTPException(404, "prediction_units.csv not found — run scripts/train_model.py")
    units = pd.read_csv(units_path)
    sample = units.sample(min(400, len(units)), random_state=7)
    X = sample[svc.features]
    return svc.shap_summary_values(X, max_display=15)


@router.get("/evaluation")
def evaluation(_user=Depends(get_current_user)):
    s = get_settings()
    p = os.path.join(s.artifacts_dir_resolved, "evaluation_v1.json")
    if not os.path.exists(p):
        raise HTTPException(404, "Evaluation artifact not found")
    with open(p) as f:
        return json.load(f)