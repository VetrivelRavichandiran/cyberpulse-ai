"""CYBERPULSE AI — SQLAlchemy ORM models.

Normalized schema with foreign keys, indexes and timestamps. Geospatial
columns are stored as (latitude, longitude) float pairs so the demo runs on
plain SQLite; on PostgreSQL/PostGIS the same coordinates power ST_* queries
(see docs/database.md for the PostGIS mapping).
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── enums ───────────────────────────────────────────────────────────────────
class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    I4C_ANALYST = "I4C_ANALYST"
    STATE_OFFICER = "STATE_OFFICER"
    DISTRICT_OFFICER = "DISTRICT_OFFICER"
    INVESTIGATOR = "INVESTIGATOR"
    BANK_USER = "BANK_USER"


class ComplaintStatus(str, enum.Enum):
    NEW = "NEW"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"


class AlertStatus(str, enum.Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class InvestigationStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


# ── auth ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.INVESTIGATOR)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── domain: complaints / accounts / transactions / atms ─────────────────────
class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        Index("ix_complaints_ts", "timestamp"),
        Index("ix_complaints_district", "victim_district"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    crime_category: Mapped[str] = mapped_column(String(40))
    subcategory: Mapped[str | None] = mapped_column(String(60), nullable=True)
    victim_state: Mapped[str] = mapped_column(String(60))
    victim_district: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    reported_amount: Mapped[float] = mapped_column(Float, default=0.0)
    phone_hash: Mapped[str | None] = mapped_column(String(60), nullable=True)
    account_hash: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[ComplaintStatus] = mapped_column(Enum(ComplaintStatus), default=ComplaintStatus.NEW)
    ring_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ground truth (synthetic)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    bank_id: Mapped[str] = mapped_column(String(10), index=True)
    risk_indicator: Mapped[str] = mapped_column(String(20), default="NORMAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(60))
    district: Mapped[str] = mapped_column(String(80))


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_ts", "timestamp"),
        Index("ix_transactions_account", "account_id"),
        Index("ix_transactions_atm", "atm_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    account_id: Mapped[str] = mapped_column(String(20))
    beneficiary_account_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    transaction_type: Mapped[str] = mapped_column(String(24))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    atm_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    ring_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ground truth (synthetic)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ATM(Base):
    __tablename__ = "atms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    atm_id: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    bank_id: Mapped[str] = mapped_column(String(10))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    district: Mapped[str] = mapped_column(String(80), index=True)
    state: Mapped[str] = mapped_column(String(60))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── graph ───────────────────────────────────────────────────────────────────
class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), index=True)  # PHONE/ACCOUNT/ATM/DISTRICT/BANK
    masked_identifier: Mapped[str] = mapped_column(String(120))


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"
    __table_args__ = (
        Index("ix_rel_source", "source_entity"),
        Index("ix_rel_target", "target_entity"),
        UniqueConstraint("source_entity", "target_entity", "relationship_type", name="uq_rel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_entity: Mapped[str] = mapped_column(String(20))
    target_entity: Mapped[str] = mapped_column(String(20))
    relationship_type: Mapped[str] = mapped_column(String(30))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


# ── predictions ─────────────────────────────────────────────────────────────
class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_predictions_ts", "window_start"),
        Index("ix_predictions_risk", "risk_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    atm_id: Mapped[str] = mapped_column(String(12), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    probability: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    factors: Mapped[list["PredictionFactor"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan", order_by="PredictionFactor.rank"
    )


class PredictionFactor(Base):
    __tablename__ = "prediction_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("predictions.prediction_id"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer, default=0)
    feature: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(120))
    impact: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(12))

    prediction: Mapped[Prediction] = relationship(back_populates="factors")


# ── alerts ──────────────────────────────────────────────────────────────────
class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status", "status"), Index("ix_alerts_created", "created_at"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity))
    prediction_id: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    atm_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.NEW)
    assigned_to: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ── investigations ──────────────────────────────────────────────────────────
class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = (Index("ix_inv_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[InvestigationStatus] = mapped_column(
        Enum(InvestigationStatus), default=InvestigationStatus.OPEN
    )
    priority: Mapped[str] = mapped_column(String(12), default="MEDIUM")
    assigned_to: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    alert_id: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    prediction_id: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[list["InvestigationNote"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", order_by="InvestigationNote.created_at"
    )
    timeline: Mapped[list["TimelineEvent"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", order_by="TimelineEvent.occurred_at"
    )
    interventions: Mapped[list["Intervention"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )


class InvestigationNote(Base):
    __tablename__ = "investigation_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(24), ForeignKey("investigations.case_id"), index=True)
    author: Mapped[str] = mapped_column(String(80))
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    investigation: Mapped[Investigation] = relationship(back_populates="notes")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    __table_args__ = (Index("ix_timeline_case", "case_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(24), ForeignKey("investigations.case_id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    investigation: Mapped[Investigation] = relationship(back_populates="timeline")


class Intervention(Base):
    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(24), ForeignKey("investigations.case_id"), index=True)
    action_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    performed_by: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    investigation: Mapped[Investigation] = relationship(back_populates="interventions")


# ── audit / notifications / model runs ──────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_ts", "timestamp"), Index("ix_audit_user", "username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    username: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), default="in_app")  # in_app/websocket/email/webhook
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(12), default="INFO")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(20), unique=True)
    algorithm: Mapped[str] = mapped_column(String(40))
    dataset_version: Mapped[str] = mapped_column(String(40))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metrics_json: Mapped[str] = mapped_column(Text)
    feature_importance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)