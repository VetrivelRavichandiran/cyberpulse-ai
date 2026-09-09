#!/usr/bin/env python3
"""Build prediction units, train + evaluate models, save artifacts."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ml.preprocessing.features import build_prediction_units, load_raw, FEATURES  # noqa: E402
from ml.training.train import train  # noqa: E402

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--artifacts", default=os.path.join(ROOT, "ml", "artifacts"))
    args = ap.parse_args()

    data = load_raw(args.data)
    units = build_prediction_units(data)
    os.makedirs(os.path.join(ROOT, "data", "processed"), exist_ok=True)
    units.to_csv(os.path.join(ROOT, "data", "processed", "prediction_units.csv"), index=False)
    print(f"[train] prediction units: {len(units)}  positive rate: {units.y.mean():.3f}")

    reg = train(units, artifact_dir=args.artifacts,
                dataset_version=data.get("meta", {}).get("dataset_version", "synthetic-v1"))
    a, b = reg["active"]["metrics"]["test"], reg["baseline"]["metrics"]["test"]
    print(f"[train] XGBoost test  AUC={a['roc_auc']:.3f} F1={a['f1']:.3f} "
          f"P={a['precision']:.3f} R={a['recall']:.3f} hotspot_rate={a['hotspot_detection_rate']:.3f}")
    print(f"[train] LogReg  test  AUC={b['roc_auc']:.3f} F1={b['f1']:.3f} "
          f"P={b['precision']:.3f} R={b['recall']:.3f}")
    print(f"[train] threshold={reg['active']['threshold']:.2f} "
          f"split={reg['split_sizes']} pos_rate_test={reg['positive_rate_test']:.3f}")

    # anomaly detector (Isolation Forest) on the training feature space
    import numpy as np
    from sklearn.ensemble import IsolationForest
    import joblib
    tr = units.sort_values("window_start").head(int(len(units) * 0.6))
    Xtr = tr[FEATURES].values
    iso = IsolationForest(n_estimators=150, contamination=0.05, random_state=42, n_jobs=4).fit(Xtr)
    joblib.dump({"model": iso, "contamination": 0.05}, os.path.join(args.artifacts, "anomaly_v1.joblib"))
    print(f"[train] anomaly detector fitted on {len(tr)} units -> anomaly_v1.joblib")

    print(f"[train] artifacts written to {args.artifacts}")