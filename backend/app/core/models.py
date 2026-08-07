"""SQLAlchemy entities — see docs/05-data-architecture.md.

JSON columns store flexible payloads (features, evidence ids, series) while the
relational columns stay queryable. Provenance is mandatory on predictions/alerts.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String, default="Chennai")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    elevation_m: Mapped[float] = mapped_column(Float, default=0)
    drainage_capacity_mmh: Mapped[float] = mapped_column(Float, default=8.0)
    population: Mapped[int] = mapped_column(Integer, default=0)
    hazard_type: Mapped[str] = mapped_column(String, default="flood")
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # satellite | weather | civic | citizen | news | model
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rainfall_mm: Mapped[float] = mapped_column(Float, default=0)
    rain_forecast_mm: Mapped[float] = mapped_column(Float, default=0)
    humidity: Mapped[float] = mapped_column(Float, default=0)
    wind_kmh: Mapped[float] = mapped_column(Float, default=0)
    source_id: Mapped[str] = mapped_column(String)


class IngestedDatum(Base):
    """Typed telemetry archive — holds adapter frames that don't map to a
    canonical table (reservoir storage/release, gauge levels, …). Keeps a
    per-row synthetic flag so provenance stays honest when live feeds attach."""

    __tablename__ = "ingested_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_id: Mapped[str] = mapped_column(String)
    metric: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String, default="")
    is_synthetic: Mapped[bool] = mapped_column(default=True)


class SatelliteFrame(Base):
    __tablename__ = "satellite_frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    soil_moisture_anomaly: Mapped[float] = mapped_column(Float, default=0)
    surface_water_index: Mapped[float] = mapped_column(Float, default=0)
    source_id: Mapped[str] = mapped_column(String)


class CitizenReport(Base):
    __tablename__ = "citizen_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    category: Mapped[str] = mapped_column(String)  # flooding | drain_blocked | waterlogging
    severity_hint: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(default=False)
    source_id: Mapped[str] = mapped_column(String)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    event_type: Mapped[str] = mapped_column(String, index=True)  # flood | wildfire | dumping
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[int] = mapped_column(Integer, default=0)  # 0-5
    status: Mapped[str] = mapped_column(String, default="forming")
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    event_type: Mapped[str] = mapped_column(String, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    horizon_h: Mapped[int] = mapped_column(Integer, default=24)
    risk_probability: Mapped[float] = mapped_column(Float, default=0)
    severity: Mapped[float] = mapped_column(Float, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    lower_bound: Mapped[float] = mapped_column(Float, default=0)
    upper_bound: Mapped[float] = mapped_column(Float, default=1)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    attribution: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    model_name: Mapped[str] = mapped_column(String, default="earthpulse-stream-v1")
    series: Mapped[dict] = mapped_column(JSON, default=dict)  # forecast curve + bands


class EvidenceObject(Base):
    __tablename__ = "evidence_objects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"), nullable=True)
    source_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # observation | forecast | report | citation
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    event_type: Mapped[str] = mapped_column(String, index=True)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String, default="advisory")  # advisory|watch|warning|critical
    title: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(default=False)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"), nullable=True)


class Intervention(Base):
    __tablename__ = "interventions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # engineering | operational | policy
    default_intensity: Mapped[float] = mapped_column(Float, default=0.5)
    description: Mapped[str] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    event_type: Mapped[str] = mapped_column(String, default="flood")
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)  # before/after + deltas


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    agent: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    role: Mapped[str] = mapped_column(String, default="producer")  # producer|receiver|verdict
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    used_sources: Mapped[list] = mapped_column(JSON, default=list)
    failure: Mapped[str | None] = mapped_column(Text, nullable=True)


class PulseScore(Base):
    __tablename__ = "pulse_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    score: Mapped[float] = mapped_column(Float, default=1000)
    factors: Mapped[dict] = mapped_column(JSON, default=dict)


# ---- NextGen: field intel (ground-truth loop) ------------------------------

class FieldReport(Base):
    """Crowd-sourced ground-truth signal — the verification loop SMS lacks.

    A report carries observed severity + geo; the system auto-scores agreement
    against the latest model prediction for the nearest zone (corroboration),
    so operators can confirm/dismiss from a ranked feed.
    """

    __tablename__ = "field_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    hazard_type: Mapped[str] = mapped_column(String, default="flood")
    observed_severity: Mapped[int] = mapped_column(Integer, default=1)  # 0-5 observed impact
    description: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float, default=0)
    lon: Mapped[float] = mapped_column(Float, default=0)
    distance_km: Mapped[float] = mapped_column(Float, default=0)  # to nearest zone centroid
    agreement: Mapped[float] = mapped_column(Float, default=0)  # 0..1 with model prediction
    model_risk: Mapped[float] = mapped_column(Float, default=0)  # nearest-zone risk at report time
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | confirmed | dismissed
    medium: Mapped[str] = mapped_column(String, default="web")  # web | sms | copilot | phone
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    reporter: Mapped[str | None] = mapped_column(String, nullable=True)
    votes: Mapped[int] = mapped_column(Integer, default=0)
    flagged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# ---- NextGen: scenario simulator (digital twin) -----------------------------

class ScenarioRun(Base):
    """A hypothetical hazard marched across the theatre hour by hour.

    `summary` holds the what-if report (peak zones, affected population, shelter
    ledger); `steps` are per-hour frames stored in ScenarioStep so the UI can
    animate the wake without re-deriving the physics.
    """

    __tablename__ = "scenario_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    hazard_type: Mapped[str] = mapped_column(String, default="cyclone")
    start_lat: Mapped[float] = mapped_column(Float)
    start_lon: Mapped[float] = mapped_column(Float)
    end_lat: Mapped[float] = mapped_column(Float)
    end_lon: Mapped[float] = mapped_column(Float)
    intensity: Mapped[float] = mapped_column(Float, default=1.0)  # 0-1
    radius_km: Mapped[float] = mapped_column(Float, default=120)
    duration_h: Mapped[int] = mapped_column(Integer, default=12)
    step_h: Mapped[int] = mapped_column(Integer, default=1)
    zoom_h: Mapped[int] = mapped_column(Integer, default=3)  # sprint interval (0 = no zoom)
    status: Mapped[str] = mapped_column(String, default="done")  # queued | running | done
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ScenarioStep(Base):
    """One frame of a scenario run — the zone snapshot at hour t."""

    __tablename__ = "scenario_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("scenario_runs.id"), index=True)
    t_index: Mapped[int] = mapped_column(Integer, index=True)
    frame: Mapped[dict] = mapped_column(JSON, default=dict)  # {t, zones:[{id,name,lat,lon,p,level}], peak, crisis}


class GhostAction(Base):
    """Audit record for the autonomous escalation agent (Ghost Mode)."""

    __tablename__ = "ghost_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String, default="sms_broadcast")  # sms_broadcast | scenario_broadcast | escalation
    detail: Mapped[str] = mapped_column(Text)
    recipients: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PushSubscription(Base):
    """Browser push subscription (Web Push / RFC 8291) for offline alerts."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)  # base64url client public key
    auth: Mapped[str] = mapped_column(Text)  # base64url auth secret
    ua: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PushKey(Base):
    """Persisted VAPID keypair so subscriptions survive app restarts."""

    __tablename__ = "push_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    private_pem: Mapped[str] = mapped_column(Text)
    public_pem: Mapped[str] = mapped_column(Text)
