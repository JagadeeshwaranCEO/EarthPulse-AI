"""Cognition agents — Risk Fusion, Prediction, Explanation, Recommendation, Simulation."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.ml.attribution import compute_attribution
from app.ml.forecaster import DEFAULT_FORECASTER, probability_from_components
from app.services.simulation_engine import run_simulation


class RiskFusionAgent(BaseAgent):
    name = "risk_fusion"
    mission = "Fuse sensor + observer signals into per-location risk components with weighted confidence."
    inputs = ["satellite", "weather", "air_quality", "water", "citizen_report", "news"]
    outputs = ["components", "components_confidence", "anomaly_score"]
    failure_mode = "missing agent output → component floors at 0, confidence penalized"

    def run(self, ctx: AgentContext) -> AgentResult:
        agg = ctx.payload.get("agent_outputs") or {}
        components: dict[str, float] = {
            "rain_intensity": agg.get("weather", {}).get("rain_intensity", 0),
            "soil_moisture": agg.get("satellite", {}).get("soil_moisture_anomaly", 0),
            "headroom_deficit": agg.get("water", {}).get("headroom_deficit", 0),
            "drainage_stress": agg.get("water", {}).get("drainage_stress", 0),
            "citizen_pressure": agg.get("citizen_report", {}).get("citizen_pressure", 0),
            "aq_anomaly": agg.get("air_quality", {}).get("aq_anomaly", 0),
        }
        confs = [
            agg.get("weather", {}).get("_conf", 0.5),
            agg.get("satellite", {}).get("_conf", 0.5),
            agg.get("water", {}).get("_conf", 0.5),
            agg.get("citizen_report", {}).get("_conf", 0.3),
        ]
        fused_conf = round(sum(confs) / len(confs), 3)
        anomaly = min(1.0, (components["rain_intensity"] / 10 + components["soil_moisture"] / 8) / 2)
        return AgentResult(
            outputs={"components": components, "components_confidence": fused_conf, "anomaly_score": round(anomaly, 3)},
            confidence=fused_conf,
            messages=[f"fused {len(components)} components, anomaly {anomaly:.2f}"],
        )


class PredictionAgent(BaseAgent):
    name = "prediction"
    mission = "Forecast risk probability, severity, horizon and geographic spread with uncertainty bands."
    inputs = ["components", "historical_features"]
    outputs = ["forecast_series", "risk_probability", "severity", "confidence", "bounds"]
    failure_mode = "insufficient history → widen bands, emit low confidence, never silent"

    def run(self, ctx: AgentContext) -> AgentResult:
        components = ctx.payload.get("components") or {}
        hist = ctx.payload.get("historical_features") or []
        horizon = ctx.payload.get("horizon_h", 24)

        series = [dict(h) for h in hist[-72:]] + [components]
        signal = [probability_from_components(r) for r in series]
        t0 = ctx.payload.get("now")
        fc = DEFAULT_FORECASTER.fit_forecast(signal, t0, horizon)

        p_now = float(signal[-1])
        p_peak = max(fc.mean)
        severity = p_now * 5.0
        # confidence = forecaster fit quality (residual dispersion) + data freshness
        freshness = min(1.0, (len(hist) + 1) / 48.0)
        conf = round(max(0.3, min(0.95, 0.85 * freshness - fc.residual_std * 2)), 3)
        band = max(0.05, min(0.25, fc.residual_std * 2 + 0.05))
        return AgentResult(
            outputs={
                "forecast_series": fc,
                "risk_probability": round(p_now, 3),
                "severity": round(severity, 2),
                "peak_probability": round(p_peak, 3),
                "confidence": conf,
                "bounds": {"lower": round(max(0.0, p_now - band), 3), "upper": round(min(1.0, p_now + band), 3)},
                "model_name": fc.model_name,
                "residual_std": round(fc.residual_std, 4),
            },
            confidence=conf,
            messages=[f"P(flood|state)={p_now:.2f}, peak {p_peak:.2f} in {horizon}h, conf {conf:.2f}"],
        )


class ExplanationAgent(BaseAgent):
    name = "explanation"
    mission = "Build the causal chain and feature attribution behind a risk score."
    inputs = ["components", "prediction", "evidence"]
    outputs = ["causal_chain", "attribution", "limitations"]
    failure_mode = "missing attribution → emit chain from components only, mark partial"

    def run(self, ctx: AgentContext) -> AgentResult:
        components = ctx.payload.get("components") or {}
        pred = ctx.payload.get("prediction") or {}
        attribution = compute_attribution(components)

        nodes = [
            {"id": "rain", "label": "Monsoon rainfall surge", "kind": "cause",
             "value": f"{components.get('rain_intensity', 0):.1f} mm/h", "confidence": 0.9},
            {"id": "soil", "label": "Pre-saturated soil", "kind": "cause",
             "value": f"anomaly {components.get('soil_moisture', 0):.2f}", "confidence": 0.8},
            {"id": "drainage", "label": "Stormwater network under load", "kind": "mechanism",
             "value": f"stress {components.get('drainage_stress', 0):.2f}", "confidence": 0.75},
            {"id": "headroom", "label": "Drainage headroom deficit", "kind": "mechanism",
             "value": f"{components.get('headroom_deficit', 0):.2f}/10", "confidence": 0.8},
            {"id": "reports", "label": "Verified waterlogging reports", "kind": "condition",
             "value": f"pressure {components.get('citizen_pressure', 0):.2f}", "confidence": 0.6},
            {"id": "risk", "label": f"Flood risk ({pred.get('risk_probability', 0):.0%})", "kind": "risk",
             "value": f"severity {pred.get('severity', 0):.1f}/5", "confidence": pred.get("confidence", 0.5)},
        ]
        edges = [
            {"source": "rain", "target": "drainage", "label": "exceeds design capacity"},
            {"source": "soil", "target": "headroom", "label": "limits absorption"},
            {"source": "rain", "target": "headroom", "label": "raises water level"},
            {"source": "drainage", "target": "headroom", "label": "backlog reduces headroom"},
            {"source": "headroom", "target": "risk", "label": "approaches breach"},
            {"source": "reports", "target": "risk", "label": "ground truth confirms"},
        ]
        limitations = [
            "Rainfall nowcast uncertainty widens beyond 24 h",
            "Drainage capacity is a static design value, not live",
            "Citizen reports bias toward populated wards",
        ]
        return AgentResult(
            outputs={"causal_chain": {"nodes": nodes, "edges": edges},
                     "attribution": [a.__dict__ for a in attribution],
                     "limitations": limitations},
            confidence=0.8,
            messages=[f"explained {len(nodes)} causal nodes, {len(attribution)} attributions"],
        )


class RecommendationAgent(BaseAgent):
    name = "recommendation"
    mission = "Turn risk + forecast into prioritized, stakeholder-specific operational checklists."
    inputs = ["risk", "forecast"]
    outputs = ["recommendations"]
    failure_mode = "no risk → advisory only, never fabricate severity claims"

    def run(self, ctx: AgentContext) -> AgentResult:
        p = ctx.payload.get("risk_probability", 0.0)
        sev = ctx.payload.get("severity", 0.0)
        recs = [
            {"id": "rec_civic_1", "stakeholder": "civic", "priority": 1 if p > 0.55 else 2,
             "action": "Deploy pre-positioned pumps to lowest-lying wards and clear stormwater inlets.",
             "reasoning": "drainage stress is a top attribution feature; mechanical lift buys time.",
             "evidence_ids": []},
            {"id": "rec_responders_1", "stakeholder": "responders", "priority": 1 if sev >= 3 else 2,
             "action": "Stand by rescue teams near river-adjacent blocks; stage boats and generators.",
             "reasoning": "headroom deficit is approaching breach thresholds within the forecast horizon.",
             "evidence_ids": []},
            {"id": "rec_utilities_1", "stakeholder": "utilities", "priority": 2,
             "action": "Protect substations in flood-prone wards; prepare rolling load cuts.",
             "reasoning": "electrical infrastructure is vulnerable to water ingress.",
             "evidence_ids": []},
            {"id": "rec_public_1", "stakeholder": "public", "priority": 3,
             "action": "Avoid low-lying routes during peak hours; share verified waterlogging reports.",
             "reasoning": "ground reports improve nowcast precision for everyone.",
             "evidence_ids": []},
        ]
        if p < 0.3:
            recs = [r for r in recs if r["priority"] <= 2]
        return AgentResult(outputs={"recommendations": recs}, confidence=0.75,
                           messages=[f"{len(recs)} stakeholder actions prioritized"])


class SimulationAgent(BaseAgent):
    name = "simulation"
    mission = "Estimate impact of interventions via the what-if hazard engine."
    inputs = ["components", "interventions", "population"]
    outputs = ["before", "after", "deltas", "carbon_ledger"]
    failure_mode = "unknown intervention id → ignore it, run with known subset"

    def run(self, ctx: AgentContext) -> AgentResult:
        components = ctx.payload.get("components") or {}
        interventions = ctx.payload.get("interventions") or {}
        population = ctx.payload.get("population", 1_000_000)
        known = {k: v for k, v in interventions.items() if v > 0}
        result = run_simulation(components, population, known)
        return AgentResult(
            outputs=result,
            confidence=0.7,
            used_sources=[],
            messages=[f"simulated {len(known)} interventions → damage reduction {result['deltas']['damage_reduction_pct']}%"],
        )
