"""CYBERPULSE AI — anomaly detection (Isolation Forest).

Fits on the feature space of the prediction units and scores how unusual a
given (ATM, window) activity profile is. The anomaly score (0-1) feeds the
risk engine.
"""
from __future__ import annotations

import joblib
import os

import numpy as np
from sklearn.ensemble import IsolationForest

from ml.preprocessing.features import FEATURES

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "artifacts")


class AnomalyDetector:
    def __init__(self, artifact_dir: str | None = None, contamination: float = 0.05):
        self.artifact_dir = artifact_dir or ARTIFACT_DIR
        self.contamination = contamination
        self.model: IsolationForest | None = None
        self._fitted = False

    def fit(self, X: np.ndarray) -> "AnomalyDetector":
        self.model = IsolationForest(
            n_estimators=150, contamination=self.contamination, random_state=42, n_jobs=4
        )
        self.model.fit(X)
        self._fitted = True
        return self

    def save(self) -> str:
        path = os.path.join(self.artifact_dir, "anomaly_v1.joblib")
        joblib.dump({"model": self.model, "contamination": self.contamination}, path)
        return path

    def load(self) -> bool:
        path = os.path.join(self.artifact_dir, "anomaly_v1.joblib")
        if os.path.exists(path):
            bundle = joblib.load(path)
            self.model = bundle["model"]
            self._fitted = True
            return True
        return False

    @property
    def fitted(self) -> bool:
        return self._fitted

    def score(self, feature_row: dict) -> float:
        """Return anomaly score in [0, 1] (1 = most anomalous)."""
        if not self._fitted:
            return 0.0
        X = np.array([[float(feature_row.get(k, 0.0)) for k in FEATURES]])
        # decision_function: negative = anomalous. Normalize to 0..1.
        raw = -float(self.model.decision_function(X)[0])
        # map with a soft normalization (raw typically ~ -0.2..0.3)
        return float(np.clip(0.5 + raw, 0.0, 1.0))


_detector: AnomalyDetector | None = None


def get_detector(artifact_dir: str | None = None) -> AnomalyDetector:
    global _detector
    if _detector is None:
        _detector = AnomalyDetector(artifact_dir)
        _detector.load()
    return _detector


def reset_detector():
    global _detector
    _detector = None