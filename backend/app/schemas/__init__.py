"""CYBERPULSE AI — Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── auth ────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    full_name: str


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    role: str
    state: Optional[str] = None
    district: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# ── domain ──────────────────────────────────────────────────────────────────
class ComplaintOut(BaseModel):
    complaint_id: str
    timestamp: datetime
    crime_category: str
    victim_state: str
    victim_district: str
    latitude: float
    longitude: float
    reported_amount: float
    status: str

    class Config:
        from_attributes = True


class ATMOut(BaseModel):
    atm_id: str
    bank_id: str
    latitude: float
    longitude: float
    district: str
    state: str
    active: bool

    class Config:
        from_attributes = True


class TransactionOut(BaseModel):
    transaction_id: str
    timestamp: datetime
    account_id: str
    amount: float
    transaction_type: str
    atm_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str

    class Config:
        from_attributes = True


# ── predictions ─────────────────────────────────────────────────────────────
class FactorOut(BaseModel):
    rank: int
    feature: str
    label: str
    impact: float
    direction: str

    class Config:
        from_attributes = True


class PredictionOut(BaseModel):
    prediction_id: str
    atm_id: str
    window_start: datetime
    window_end: datetime
    probability: float
    risk_score: int
    confidence: float
    model_version: str
    district: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    recommended_action: Optional[str] = None
    created_at: datetime
    factors: list[FactorOut] = []

    class Config:
        from_attributes = True


class GenerateRequest(BaseModel):
    window_start: Optional[datetime] = None  # default: next 6h window
    min_risk: int = 0


# ── alerts ──────────────────────────────────────────────────────────────────
class AlertOut(BaseModel):
    alert_id: str
    severity: str
    prediction_id: Optional[str] = None
    atm_id: Optional[str] = None
    district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    risk_score: int
    title: str
    detail: Optional[str] = None
    recommended_action: Optional[str] = None
    status: str
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertActionRequest(BaseModel):
    assigned_to: Optional[str] = None


# ── investigations ──────────────────────────────────────────────────────────
class InvestigationCreate(BaseModel):
    title: str
    alert_id: Optional[str] = None
    prediction_id: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: str = "MEDIUM"
    district: Optional[str] = None
    summary: Optional[str] = None


class NoteCreate(BaseModel):
    note: str


class InterventionCreate(BaseModel):
    action_type: str
    description: str
    outcome: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str
    outcome: Optional[str] = None


class AcknowledgeAndOpen(BaseModel):
    assigned_to: Optional[str] = None


class TimelineEventOut(BaseModel):
    event_type: str
    title: str
    detail: Optional[str] = None
    occurred_at: Optional[datetime] = None
    metadata: Optional[dict] = None


class InvestigationOut(BaseModel):
    case_id: str
    title: str
    status: str
    priority: str
    assigned_to: Optional[str] = None
    created_by: Optional[str] = None
    alert_id: Optional[str] = None
    prediction_id: Optional[str] = None
    district: Optional[str] = None
    summary: Optional[str] = None
    outcome: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    notes: list[dict] = []
    timeline: list[TimelineEventOut] = []
    interventions: list[dict] = []

    class Config:
        from_attributes = True


# ── graph ───────────────────────────────────────────────────────────────────
class GraphNode(BaseModel):
    entity_id: str
    entity_type: str
    masked_identifier: str
    degree: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship_type: str
    label: Optional[str] = None


class GraphClusterOut(BaseModel):
    center: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    n_nodes: int
    n_edges: int
    hops: int
    backend: str


# ── model ───────────────────────────────────────────────────────────────────
class ModelInfoOut(BaseModel):
    version: str
    algorithm: str
    dataset_version: str
    trained_at: str
    threshold: float
    features: list[str]
    split_sizes: dict
    positive_rate_test: float
    label_definition: str
    disclaimer: str
    metrics: dict
    comparison: dict
    feature_importance: list[dict]


# ── simulation ──────────────────────────────────────────────────────────────
class WhatIfRequest(BaseModel):
    atm_id: str
    window_start: Optional[datetime] = None
    complaint_volume: float = 1.0     # multiplier on recent complaint counts
    transaction_intensity: float = 1.0  # multiplier on recent tx counts
    geographic_radius_km: float = 10.0  # radius for density features
    time_window_hours: int = 6


class WhatIfResponse(BaseModel):
    atm_id: str
    window_start: datetime
    current_risk: int
    simulated_risk: int
    difference: int
    current_probability: float
    simulated_probability: float
    current_factors: list[dict]
    simulated_factors: list[dict]
    label: str = "Simulation"


# ── misc ────────────────────────────────────────────────────────────────────
class HealthOut(BaseModel):
    status: str
    version: str
    time: datetime
    model_loaded: bool
    dependencies: dict[str, Any] = {}


class NotificationOut(BaseModel):
    id: int
    channel: str
    title: str
    body: Optional[str] = None
    severity: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DemoResetResponse(BaseModel):
    status: str
    counts: dict[str, int]


class PageOut(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int