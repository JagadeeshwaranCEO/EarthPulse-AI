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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


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
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
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
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    source_id: Mapped[str] = mapped_column(String)
    metric: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String, default="")
    is_synthetic: Mapped[bool] = mapped_column(default=True)


class SatelliteFrame(Base):
    __tablename__ = "satellite_frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    soil_moisture_anomaly: Mapped[float] = mapped_column(Float, default=0)
    surface_water_index: Mapped[float] = mapped_column(Float, default=0)
    source_id: Mapped[str] = mapped_column(String)


class CitizenReport(Base):
    __tablename__ = "citizen_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    reported_at: Mapped[datetime] = mapped_column(DateTime, index=True)
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
    started_at: Mapped[datetime] = mapped_column(DateTime)
    severity: Mapped[int] = mapped_column(Integer, default=0)  # 0-5
    status: Mapped[str] = mapped_column(String, default="forming")
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    event_type: Mapped[str] = mapped_column(String, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
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
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    description: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    event_type: Mapped[str] = mapped_column(String, index=True)
    raised_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
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
    run_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)  # before/after + deltas


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    agent: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    role: Mapped[str] = mapped_column(String, default="producer")  # producer|receiver|verdict
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    used_sources: Mapped[list] = mapped_column(JSON, default=list)
    failure: Mapped[str | None] = mapped_column(Text, nullable=True)


class PulseScore(Base):
    __tablename__ = "pulse_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    score: Mapped[float] = mapped_column(Float, default=1000)
    factors: Mapped[dict] = mapped_column(JSON, default=dict)
