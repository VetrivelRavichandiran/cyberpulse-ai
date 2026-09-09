"""CYBERPULSE AI — alert engine.

Creates alerts when a prediction's risk score crosses the configurable
threshold, persists them, and fans out notifications (in-app + websocket).
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Alert, AlertSeverity, AlertStatus, Prediction
from ..services.audit import audit
from ..services.notifications import notify
from ..services.prediction_service import risk_band

logger = logging.getLogger("cyberpulse.alerts")


def severity_for(risk: int) -> AlertSeverity:
    band = risk_band(risk)
    return AlertSeverity(band)


def create_alert_from_prediction(db: Session, pred: Prediction,
                                 threshold: float | None = None,
                                 username: str = "system") -> Alert | None:
    s = get_settings()
    threshold = threshold if threshold is not None else s.risk_alert_threshold
    if pred.risk_score < threshold:
        return None

    sev = severity_for(pred.risk_score)
    alert = Alert(
        alert_id=f"ALR-{uuid.uuid4().hex[:10].upper()}",
        severity=sev,
        prediction_id=pred.prediction_id,
        atm_id=pred.atm_id,
        district=pred.district,
        latitude=pred.latitude,
        longitude=pred.longitude,
        risk_score=pred.risk_score,
        title=f"{sev.value} risk at {pred.atm_id} ({pred.district}) — window {pred.window_start:%Y-%m-%d %H:%M}",
        detail=(
            f"Predicted suspicious withdrawal activity at {pred.atm_id} in {pred.district}. "
            f"Risk {pred.risk_score}/100 (probability {pred.probability:.2f}, "
            f"confidence {pred.confidence:.2f}). Expected window: "
            f"{pred.window_start:%Y-%m-%d %H:%M} → {pred.window_end:%Y-%m-%d %H:%M} UTC."
        ),
        recommended_action=pred.recommended_action,
        status=AlertStatus.NEW,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    logger.info("Alert created: %s severity=%s risk=%d", alert.alert_id, sev.value, pred.risk_score)

    # fan out notifications
    notify(db,
           title=f"🚨 {sev.value} alert: {pred.atm_id} ({pred.district})",
           body=alert.detail,
           severity=sev.value,
           resource=alert.alert_id)
    audit(db, username, "ALERT_CREATED", resource=alert.alert_id,
          detail=f"severity={sev.value} risk={pred.risk_score}")
    return alert


def transition(db: Session, alert: Alert, new_status: AlertStatus,
               username: str, assigned_to: str | None = None,
               result: str = "SUCCESS") -> Alert:
    alert.status = new_status
    if assigned_to:
        alert.assigned_to = assigned_to
    db.commit()
    db.refresh(alert)
    audit(db, username, f"ALERT_{new_status.value}", resource=alert.alert_id, result=result)
    notify(db, title=f"Alert {alert.alert_id} → {new_status.value}",
           body=f"Alert status changed to {new_status.value} by {username}.",
           severity="INFO", resource=alert.alert_id)
    return alert