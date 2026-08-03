"""Cognition agents — Risk Fusion, Prediction, Explanation, Recommendation, Simulation.

Hazard-parametric: every agent reads the active hazard template from the
payload (`hazard_type`) and dispatches its formula, graph or checklist through
the hazard registry. Flood stays bit-for-bit the legacy behaviour.
"""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.hazards.registry import get_hazard
from app.ml.attribution import compute_attribution
from app.ml.forecaster import DEFAULT_FORECASTER, probability_for
from app.services.simulation_engine import run_simulation


class RiskFusionAgent(BaseAgent):
    name = "risk_fusion"
    mission = "Fuse sensor + observer signals into per-location risk components with weighted confidence."
    inputs = ["satellite", "weather", "air_quality", "water", "citizen_report", "news"]
    outputs = ["components", "components_confidence", "anomaly_score"]
    failure_mode = "missing agent output → component floors at risk, confidence penalized"

    def run(self, ctx: AgentContext) -> AgentResult:
        hazard = get_hazard(ctx.payload.get("hazard_type"))
        components = hazard.fusion(ctx.payload)
        agg = ctx.payload.get("agent_outputs") or {}
        confs = [
            agg.get("weather", {}).get("_conf", 0.5),
            agg.get("satellite", {}).get("_conf", 0.5),
            agg.get("water", {}).get("_conf", 0.5),
            agg.get("citizen_report", {}).get("_conf", 0.3),
        ]
        fused_conf = round(sum(confs) / len(confs), 3)
        top = sorted(components.values(), reverse=True)[:2] or [0.0]
        anomaly = round(min(1.0, sum(top) / 24.0), 3)
        return AgentResult(
            outputs={"components": components, "components_confidence": fused_conf, "anomaly_score": anomaly},
            confidence=fused_conf,
            messages=[f"fused {len(components)} {hazard.id} components, anomaly {anomaly:.2f}"],
        )


class PredictionAgent(BaseAgent):
    name = "prediction"
    mission = "Forecast risk probability, severity, horizon and geographic spread with uncertainty bands."
    inputs = ["components", "historical_features"]
    outputs = ["forecast_series", "risk_probability", "severity", "confidence", "bounds"]
    failure_mode = "insufficient history → widen bands, emit low confidence, never silent"

    def run(self, ctx: AgentContext) -> AgentResult:
        hazard = get_hazard(ctx.payload.get("hazard_type"))
        components = ctx.payload.get("components") or {}
        hist = ctx.payload.get("historical_features") or []
        horizon = ctx.payload.get("horizon_h", 24)

        series = [dict(h) for h in hist[-72:]] + [components]
        signal = [probability_for(hazard.id, r) for r in series]
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
            messages=[f"P({hazard.id}|state)={p_now:.2f}, peak {p_peak:.2f} in {horizon}h, conf {conf:.2f}"],
        )


class ExplanationAgent(BaseAgent):
    name = "explanation"
    mission = "Build the causal chain and feature attribution behind a risk score."
    inputs = ["components", "prediction", "evidence"]
    outputs = ["causal_chain", "attribution", "limitations"]
    failure_mode = "missing attribution → emit chain from components only, mark partial"

    def run(self, ctx: AgentContext) -> AgentResult:
        hazard = get_hazard(ctx.payload.get("hazard_type"))
        components = ctx.payload.get("components") or {}
        pred = ctx.payload.get("prediction") or {}
        attribution = compute_attribution(components)
        graph = hazard.causal(components, pred) if hazard.causal else _default_causal(hazard, components, pred)
        limitations = [
            f"{hazard.id} feature inputs carry sensor-level uncertainty",
            "Forecast confidence decays beyond the operational horizon",
            "Ground-truth reports bias toward populated areas",
        ]
        return AgentResult(
            outputs={"causal_chain": graph, "attribution": [a.__dict__ for a in attribution],
                     "limitations": limitations},
            confidence=0.8,
            messages=[f"explained {len(graph['nodes'])} causal nodes, {len(attribution)} attributions"],
        )


def _default_causal(hazard, components: dict, pred: dict) -> dict:
    label = hazard.label.lower()
    top = sorted(components.items(), key=lambda kv: kv[1], reverse=True)[:3]
    nodes = [
        {"id": f"{k}", "label": hazard.features.get(k, k), "kind": "cause",
         "value": f"{v:.2f}", "confidence": 0.75}
        for k, v in top
    ]
    nodes.append({"id": "risk", "label": f"{hazard.label} risk ({pred.get('risk_probability', 0):.0%})",
                  "kind": "risk", "value": f"severity {pred.get('severity', 0):.1f}/5",
                  "confidence": pred.get("confidence", 0.5)})
    edges = [{"source": n["id"], "target": "risk", "label": "drives"} for n in nodes[:-1]]
    return {"nodes": nodes, "edges": edges}


class RecommendationAgent(BaseAgent):
    name = "recommendation"
    mission = "Turn risk + forecast into prioritized, stakeholder-specific operational checklists."
    inputs = ["risk", "forecast"]
    outputs = ["recommendations"]
    failure_mode = "no risk → advisory only, never fabricate severity claims"

    def run(self, ctx: AgentContext) -> AgentResult:
        hazard = get_hazard(ctx.payload.get("hazard_type"))
        p = ctx.payload.get("risk_probability", 0.0)
        sev = ctx.payload.get("severity", 0.0)
        recs = hazard.recommend(p, sev) if hazard.recommend else _default_recommend(p, sev)
        if p < 0.3:
            recs = [r for r in recs if r["priority"] <= 2]
        return AgentResult(outputs={"recommendations": recs}, confidence=0.75,
                           messages=[f"{len(recs)} stakeholder actions prioritized"])


def _default_recommend(p: float, sev: float) -> list:
    return [
        {"id": "rec_civic_1", "stakeholder": "civic", "priority": 1 if p > 0.55 else 2,
         "action": "Deploy pre-positioned pumps to lowest-lying wards and clear stormwater inlets.",
         "reasoning": "drainage stress is a top attribution feature; mechanical lift buys time.",
         "evidence_ids": []},
        {"id": "rec_responders_1", "stakeholder": "responders", "priority": 1 if sev >= 3 else 2,
         "action": "Stand by rescue teams near river-adjacent blocks; stage boats and generators.",
         "reasoning": "headroom deficit is approaching breach thresholds within the forecast horizon.",
         "evidence_ids": []},
        {"id": "rec_public_1", "stakeholder": "public", "priority": 3,
         "action": "Avoid low-lying routes during peak hours; share verified waterlogging reports.",
         "reasoning": "ground reports improve nowcast precision for everyone.",
         "evidence_ids": []},
    ]


class SimulationAgent(BaseAgent):
    name = "simulation"
    mission = "Estimate impact of interventions via the what-if hazard engine."
    inputs = ["components", "interventions", "population"]
    outputs = ["before", "after", "deltas", "carbon_ledger"]
    failure_mode = "unknown intervention name → ignore it, run with known subset"

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