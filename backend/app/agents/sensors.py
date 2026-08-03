"""Sensing agents — Satellite, Weather, Air Quality, Water.

Each agent reads a slice of the ingested state (via payload built by the
orchestrator from DB) and produces typed signals with confidence and provenance.
"""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent


class SatelliteAgent(BaseAgent):
    name = "satellite"
    mission = "Detect soil moisture and surface water anomalies from satellite-style frames."
    inputs = ["satellite_frames"]
    outputs = ["soil_moisture_anomaly", "surface_water_index"]
    failure_mode = "stale frames → widen uncertainty, do not fabricate wetness"

    def run(self, ctx: AgentContext) -> AgentResult:
        frames = ctx.payload.get("satellite_frames") or []
        if not frames:
            return AgentResult(confidence=0.2, failure="no satellite frames available", outputs={"soil_moisture_anomaly": 0, "surface_water_index": 0})
        latest = frames[-1]
        anomaly = latest.get("soil_moisture_anomaly", 0.0)
        swi = latest.get("surface_water_index", 0.0)
        return AgentResult(
            outputs={"soil_moisture_anomaly": anomaly, "surface_water_index": swi},
            confidence=min(0.95, 0.6 + 0.3 * min(1.0, len(frames) / 24.0)),
            messages=[f"detected soil moisture anomaly {anomaly:.2f}, surface water index {swi:.2f}"],
            used_sources=[f["source_id"] for f in frames[-3:]],
        )


class WeatherAgent(BaseAgent):
    name = "weather"
    mission = "Nowcast rainfall accumulation and forecast pressure from gauge + forecast series."
    inputs = ["weather_snapshots"]
    outputs = ["rain_intensity", "rain_forecast_mm", "humidity"]
    failure_mode = "missing gauge → use forecast only with reduced confidence"

    def run(self, ctx: AgentContext) -> AgentResult:
        snaps = ctx.payload.get("weather_snapshots") or []
        if not snaps:
            return AgentResult(confidence=0.15, failure="no weather snapshots", outputs={"rain_intensity": 0, "rain_forecast_mm": 0, "humidity": 0})
        recent = snaps[-6:]
        accumulation = sum(s.get("rainfall_mm", 0) for s in recent)
        exposure = ctx.payload.get("exposure", 1.0)
        intensity = min(12.0, accumulation / 16.0 * exposure)  # 6h accumulation vs design stress
        forecast = snaps[-1].get("rain_forecast_mm", 0.0)
        humidity = snaps[-1].get("humidity", 0.0)
        return AgentResult(
            outputs={"rain_intensity": round(intensity, 2), "rain_forecast_mm": forecast, "humidity": humidity},
            confidence=min(0.9, 0.5 + 0.3 * min(1.0, len(snaps) / 48.0)),
            messages=[f"6-window rain intensity {intensity:.2f} mm/h, forecast {forecast:.1f} mm"],
            used_sources=[snaps[-1]["source_id"]],
        )


class AirQualityAgent(BaseAgent):
    name = "air_quality"
    mission = "Surface AQ anomalies (context signal for haze and urban heat coupling)."
    inputs = ["aq_stream"]
    outputs = ["aq_anomaly"]
    failure_mode = "no AQ data → neutral context, confidence floors at 0.3"

    def run(self, ctx: AgentContext) -> AgentResult:
        aq = ctx.payload.get("aq_stream") or []
        if not aq:
            return AgentResult(confidence=0.3, outputs={"aq_anomaly": 0.0}, messages=["no AQ stream; neutral context"])
        latest = aq[-1].get("aqi_anomaly", 0.0)
        return AgentResult(confidence=0.7, outputs={"aq_anomaly": latest}, used_sources=[aq[-1].get("source_id", "")], messages=[f"AQ anomaly {latest:.2f}"])


class WaterAgent(BaseAgent):
    name = "water"
    mission = "Track river/canal level vs drainage headroom; flag breach pressure."
    inputs = ["water_level_series", "drainage_capacity_mmh"]
    outputs = ["headroom_deficit", "drainage_stress", "breach_risk"]
    failure_mode = "gauge offline → extrapolate level with +0.15 uncertainty, flag degraded"

    def run(self, ctx: AgentContext) -> AgentResult:
        levels = ctx.payload.get("water_level_series") or []
        capacity = ctx.payload.get("drainage_capacity_mmh", 8.0)
        if not levels:
            return AgentResult(confidence=0.2, failure="gauge offline", outputs={"headroom_deficit": 0, "drainage_stress": 0, "breach_risk": 0})
        latest = levels[-1]
        headroom_deficit = float(latest.get("headroom_deficit", 0.0))
        stress = float(latest.get("drainage_stress", 0.0))
        if "headroom_deficit" not in latest:
            current = latest.get("level_m", 0.0)
            headroom_m = max(0.0, latest.get("capacity_m", 1.0) - current)
            headroom_deficit = max(0.0, 6.0 - headroom_m * 6.0)
            stress = min(10.0, latest.get("inflow_m3s", 0.0) / max(1.0, capacity * 40))
        return AgentResult(
            outputs={
                "headroom_deficit": round(headroom_deficit, 2),
                "drainage_stress": round(stress, 2),
                "breach_risk": round(min(1.0, headroom_deficit / 12.0), 3),
            },
            confidence=0.85 if latest.get("source_ok", True) else 0.55,
            used_sources=[latest["source_id"]],
            messages=[f"headroom deficit {headroom_deficit:.2f}, drainage stress {stress:.2f}"],
        )
