"""CYBERPULSE AI — prediction & risk engine (backend service).

Pipeline per (ATM, window):
  1. Compute point-in-time features (FeatureContext — identical to training)
  2. ML probability (XGBoost artifact)
  3. Anomaly score (Isolation Forest)
  4. Graph score (network signals from relationships)
  5. Temporal + history scores
  6. Combined risk score 0-100 (configurable weights)
  7. SHAP explanation
  8. Persist Prediction + PredictionFactor rows

The FeatureContext is built from the database (not the CSVs), so live
predictions always reflect current DB state — including simulation events.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Alert, ATM, Account, Complaint, Entity, EntityRelationship, Prediction, PredictionFactor, Transaction
from .anomaly import get_detector
from ml.inference.service import get_service
from ml.preprocessing.features import FeatureContext

logger = logging.getLogger("cyberpulse.predict")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.svc = get_service(
            artifact_dir=self.settings.artifacts_dir_resolved,
            model_path=self.settings.model_path_resolved,
            risk_weights=self.settings.risk_weights,
            alert_threshold=self.settings.risk_alert_threshold,
            boost_factor=self.settings.risk_boost_factor,
        )
        self.detector = get_detector(self.settings.artifacts_dir_resolved)

    # ── context ────────────────────────────────────────────────────────────
    def build_context(self) -> FeatureContext:
        """Build a FeatureContext from current DB contents."""
        complaints = self.db.execute(select(Complaint)).scalars().all()
        transactions = self.db.execute(select(Transaction)).scalars().all()
        atms = self.db.execute(select(ATM)).scalars().all()
        accounts = self.db.execute(select(Account)).scalars().all()
        entities = self.db.execute(select(Entity)).scalars().all()
        rels = self.db.execute(select(EntityRelationship)).scalars().all()

        cdf = pd.DataFrame([
            {"timestamp": c.timestamp, "latitude": c.latitude, "longitude": c.longitude}
            for c in complaints
        ])
        tdf = pd.DataFrame([
            {"timestamp": t.timestamp, "transaction_type": t.transaction_type,
             "account_id": t.account_id, "beneficiary_account_id": t.beneficiary_account_id or "",
             "amount": t.amount, "latitude": t.latitude, "longitude": t.longitude,
             "atm_id": t.atm_id or "", "status": t.status}
            for t in transactions
        ])
        adf = pd.DataFrame([
            {"atm_id": a.atm_id, "latitude": a.latitude, "longitude": a.longitude} for a in atms
        ])
        acdf = pd.DataFrame([{"account_id": a.account_id, "risk_indicator": a.risk_indicator}
                             for a in accounts])
        edf = pd.DataFrame([{"entity_id": e.entity_id, "entity_type": e.entity_type,
                             "masked_identifier": e.masked_identifier} for e in entities])
        rdf = pd.DataFrame([{"source_entity": r.source_entity, "target_entity": r.target_entity,
                             "relationship_type": r.relationship_type, "timestamp": r.timestamp}
                            for r in rels])
        # origin: earliest complaint (or fixed demo origin)
        origin = min((c.timestamp for c in complaints), default=datetime(2026, 1, 1, tzinfo=timezone.utc))
        origin = origin.replace(tzinfo=None) if origin.tzinfo else origin
        days = 45
        return FeatureContext(cdf, tdf, adf, acdf, edf, rdf, origin, days)

    # ── graph / temporal / history scores ──────────────────────────────────
    def graph_score(self, atm_id: str, window_start: datetime) -> float:
        """0-1 score from network signals: suspicious neighbors, mule inflow, degree."""
        ctx_features = None
        # suspicious ratio + mule inflow + degree (already computed as features)
        # We recompute lightweight signals here from the context feature row passed in.
        return 0.0  # replaced by caller-provided feature-based score

    def _scores_from_features(self, feat: dict) -> tuple[float, float, float]:
        """Derive (graph_score, temporal_score, history_score) in 0-1 from features."""
        # graph: suspicious neighbor ratio + mule inflow presence + degree
        conn = max(feat.get("connected_accounts", 0), 1)
        susp_ratio = feat.get("suspicious_neighbors", 0) / conn
        mule = min(feat.get("mule_inflow_72h", 0) / 5.0, 1.0)
        degree = min(feat.get("entity_degree", 0) / 20.0, 1.0)
        graph = float(min(0.5 * susp_ratio + 0.3 * mule + 0.2 * degree, 1.0))

        # temporal: complaint acceleration + weekend/hour concentration
        accel = min(max(feat.get("complaint_accel", 0), 0) / 8.0, 1.0)
        vol = min(feat.get("complaints_last_24h", 0) / 10.0, 1.0)
        temporal = float(min(0.6 * accel + 0.4 * vol, 1.0))

        # history: hotspot recurrence
        hist = min(feat.get("hotspot_freq_30d", 0) / 40.0, 1.0)
        return graph, temporal, hist

    # ── prediction ─────────────────────────────────────────────────────────
    def predict_atm(self, atm: ATM, window_start: datetime, ctx: FeatureContext,
                    persist: bool = True) -> Prediction | None:
        if not self.svc.loaded:
            logger.error("Prediction service unavailable: model not loaded")
            return None

        feat = ctx.compute(atm.atm_id, window_start)
        graph_s, temporal_s, history_s = self._scores_from_features(feat)
        anomaly_s = self.detector.score(feat) if self.detector.fitted else 0.0

        res = self.svc.predict(
            feat,
            anomaly_score=anomaly_s,
            graph_score=graph_s,
            temporal_score=temporal_s,
            history_score=history_s,
        )

        # recommended action by risk band
        action = _recommended_action(res.risk_score)

        pred = None
        if persist:
            pred = Prediction(
                prediction_id=f"PRED-{uuid.uuid4().hex[:10].upper()}",
                atm_id=atm.atm_id,
                window_start=window_start.replace(tzinfo=timezone.utc) if window_start.tzinfo is None else window_start,
                window_end=(window_start + pd.Timedelta(hours=6)).replace(tzinfo=timezone.utc)
                if (window_start + pd.Timedelta(hours=6)).tzinfo is None else window_start + pd.Timedelta(hours=6),
                probability=res.probability,
                risk_score=res.risk_score,
                confidence=res.confidence,
                model_version="1.0.0",
                district=atm.district,
                state=atm.state,
                latitude=atm.latitude,
                longitude=atm.longitude,
                recommended_action=action,
            )
            self.db.add(pred)
            self.db.flush()
            for i, f in enumerate(res.factors):
                self.db.add(PredictionFactor(
                    prediction_id=pred.prediction_id,
                    rank=i + 1,
                    feature=f["feature"],
                    label=f["label"],
                    impact=f["impact"],
                    direction=f["direction"],
                ))
            self.db.commit()
            logger.info("Prediction generated: %s risk=%d prob=%.3f",
                        pred.prediction_id, res.risk_score, res.probability)
        return pred

    def predict_all(self, window_start: datetime, persist: bool = True,
                    min_risk: int = 0) -> list[Prediction]:
        """Run predictions for all active ATMs at a window (batched, fast)."""
        if not self.svc.loaded:
            logger.error("Prediction service unavailable: model not loaded")
            return []
        ctx = self.build_context()
        atms = self.db.execute(select(ATM).where(ATM.active.is_(True))).scalars().all()
        if not atms:
            return []

        # Idempotent per window: clear any prior predictions (and their alerts)
        # for this exact window_start so re-running "generate" doesn't stack
        # duplicate rows/alerts.
        ws0 = window_start.replace(tzinfo=timezone.utc) if window_start.tzinfo is None else window_start
        old_preds = self.db.execute(
            select(Prediction).where(Prediction.window_start == ws0)
        ).scalars().all()
        if old_preds:
            old_ids = [p.prediction_id for p in old_preds]
            for a in self.db.execute(
                select(Alert).where(Alert.prediction_id.in_(old_ids))
            ).scalars().all():
                self.db.delete(a)
            for pf in self.db.execute(
                select(PredictionFactor).where(PredictionFactor.prediction_id.in_(old_ids))
            ).scalars().all():
                self.db.delete(pf)
            for p in old_preds:
                self.db.delete(p)
            self.db.commit()

        # compute features + sub-scores for all ATMs
        feats, anomaly_s, graph_s, temporal_s, history_s = [], [], [], [], []
        for atm in atms:
            f = ctx.compute(atm.atm_id, window_start)
            g, t, h = self._scores_from_features(f)
            feats.append(f)
            graph_s.append(g); temporal_s.append(t); history_s.append(h)
            anomaly_s.append(self.detector.score(f) if self.detector.fitted else 0.0)

        results = self.svc.predict_batch(
            feats,
            anomaly_scores=anomaly_s, graph_scores=graph_s,
            temporal_scores=temporal_s, history_scores=history_s,
        )

        out = []
        ws = window_start.replace(tzinfo=timezone.utc) if window_start.tzinfo is None else window_start
        we = ws + pd.Timedelta(hours=6)
        # Build every row in memory first, then write in ONE commit.
        # (prediction_id is generated up-front, so no per-row flush is needed —
        #  per-row flush/commit over a network/SQLite DB was the main cost.)
        rows = []
        for atm, res in zip(atms, results):
            pid = f"PRED-{uuid.uuid4().hex[:10].upper()}"
            pred = Prediction(
                prediction_id=pid,
                atm_id=atm.atm_id,
                window_start=ws,
                window_end=we,
                probability=res.probability,
                risk_score=res.risk_score,
                confidence=res.confidence,
                model_version="1.0.0",
                district=atm.district,
                state=atm.state,
                latitude=atm.latitude,
                longitude=atm.longitude,
                recommended_action=_recommended_action(res.risk_score),
            )
            self.db.add(pred)
            for i, f in enumerate(res.factors):
                self.db.add(PredictionFactor(
                    prediction_id=pid,
                    rank=i + 1,
                    feature=f["feature"],
                    label=f["label"],
                    impact=f["impact"],
                    direction=f["direction"],
                ))
            if res.risk_score >= min_risk:
                out.append(pred)
            rows.append(pid)
        # single commit for the whole batch
        self.db.commit()
        logger.info("Batch predictions: n=%d window=%s", len(atms), ws.isoformat())
        return out


def _recommended_action(risk: int) -> str:
    if risk >= 81:
        return ("CRITICAL: Dispatch field team to the ATM location immediately. "
                "Coordinate with the bank to place a temporary withdrawal hold on linked "
                "high-risk accounts and monitor for further cash-out attempts.")
    if risk >= 61:
        return ("HIGH: Assign an investigator, verify the linked accounts and complaint "
                "cluster, and prepare for possible on-site monitoring at the predicted window.")
    if risk >= 31:
        return ("MODERATE: Add the location to the watchlist and re-evaluate at the next "
                "window. Correlate with nearby complaint activity.")
    return "LOW: No immediate action. Continue routine monitoring."


def risk_band(risk: int) -> str:
    if risk >= 81:
        return "CRITICAL"
    if risk >= 61:
        return "HIGH"
    if risk >= 31:
        return "MODERATE"
    return "LOW"