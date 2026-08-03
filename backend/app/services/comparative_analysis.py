"""Comparative Live Analysis — current telemetry vs the historical record.

Pulls the zone's live fused components, re-runs them against every archived
historical event signature (driver-by-driver delta), adds the 48h→24h evolution
arc from the replay engine, and renders a deterministic analyst verdict + a
markdown report. No LLM — every sentence is a rule over engine numbers.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.agents.orchestrator import build_agent_outputs
from app.core.models import Location, Prediction
from app.services.environmental_memory import (
    _reliability, analogue_matches, memory_for,
)
from app.services.risk_evolution import evolution as risk_evolution

_LABELS = {
    "rain_intensity": "Rainfall intensity",
    "soil_moisture": "Soil saturation",
    "headroom_deficit": "Drainage headroom",
    "drainage_stress": "Drainage overload",
}


def _level(p: float) -> str:
    return levels_for("flood", p)


def levels_for(hazard_id: str, p: float) -> str:
    from app.hazards.levels import level_for

    return level_for(hazard_id, p)


def _driver_deltas(components: dict, signature: dict, hazard_id: str = "flood") -> list[dict]:
    from app.hazards.registry import get_hazard

    labels = get_hazard(hazard_id).features
    out = []
    for k, label in labels.items():
        cur = components.get(k, 0.0)
        ref = signature.get(k, 0.0)
        ratio = cur / ref if ref > 0 else 0.0
        out.append({
            "feature": k, "driver": label,
            "current": round(cur, 2), "analogue": ref, "delta": round(cur - ref, 2),
            "matched": ratio >= 0.7,
            "direction": "worse" if cur > ref else "better",
        })
    return out


def _trend(delta_24h: float) -> str:
    if delta_24h > 0.03:
        return "rising"
    if delta_24h < -0.03:
        return "easing"
    return "steady"


def _verdict(analogues: list[dict], ev: dict) -> dict:
    top = analogues[0] if analogues else None
    if not top:
        return {
            "title": "No archived analogue aligns with current telemetry.",
            "tone": "amber",
            "advice": ("Reply through the robustness-first plan (Gamma); with no historical "
                       "transfer signal, rainfall-variance resilience outweighs analogue transfer."),
        }
    sim = top["similarity"]
    n_match = top["matching_drivers"]
    if sim >= 0.7 and n_match >= 3:
        tone = "red"
        title = f"Strong analogue match — {top['event']} ({top['date']}) presents at {sim:.0%}."
        advice = ("Historical playbook transfers. Hold the lives-first stance; divergence "
                  "mitigations apply only where structural change is flagged.")
    elif sim >= 0.55 and n_match >= 2:
        tone = "amber"
        title = (f"Partial analogue — {top['event']} ({top['date']}) aligns at {sim:.0%} "
                 f"but the theatre diverges.")
        advice = ("Blend the historical playbook with divergence mitigations; the 24h "
                  f"trajectory is {_trend(ev.get('delta_24h', 0))} — keep readiness high.")
    else:
        tone = "blue"
        title = f"Weak analogue signal ({sim:.0%}); today diverges from archived events."
        advice = ("Robustness-first: the Gamma plan plus the rainfall-variance decision "
                  "confidence should override any extrapolation from historical tenure.")
    return {"title": title, "tone": tone, "advice": advice,
            "delta_24h": round(ev.get("delta_24h", 0), 3)}


def _render_markdown(loc, comps, pred, analogues, ev, mem, verdict, previous) -> str:
    p = pred.get("risk_probability", 0.0)
    level = levels_for(loc.hazard_type, p)
    lines = [
        f"# Live Analysis — {loc.name} · {loc.region}",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · sim hour {ev['now_hour']}",
        "",
        "## 1 · Live state",
        f"- **Risk probability {p:.0%}** ({level}) · severity {pred.get('severity', 0):.1f}/5 · "
        f"confidence {pred.get('confidence', 0):.0%}",
        f"- Fused components: "
        + " · ".join(f"{_LABELS.get(k, k)} {v:.2f}" for k, v in comps.items() if k in _LABELS),
        "",
        "## 2 · Historical record (10-yr memory)",
        f"- {mem.floods_10y} recorded inundation events in the past decade.",
        f"- Known vulnerabilities: {_beautify(mem.vulnerabilities)}",
        f"- Choke points: {_beautify(mem.choke_points)}",
    ]
    if previous:
        lines.append(f"- Previous saved predictions: "
                     + ", ".join(f"{r['generated_at'][:16].replace('T', ' ')} p={r['risk_probability']:.0%}"
                                 for r in previous))
    lines += ["", "## 3 · Live vs archived analogues"]
    for a in analogues:
        lines.append(
            f"- **{a['event']} ({a['date']})** — similarity **{a['similarity'] * 100:.0f}%**, "
            f"severity {a['severity']}/5, reliability {a['reliability']}, "
            f"{a['matching_drivers']}/4 drivers matched."
        )
        for d in a["drivers"]:
            mark = "✓" if d["matched"] else "✗"
            lines.append(f"  - {mark} {d['driver']}: now {d['current']:.1f} vs {d['analogue']:.1f} "
                         f"({'+' if d['delta'] >= 0 else ''}{d['delta']:.2f}) "
                         f"[{'worse' if d['direction'] == 'worse' else 'recovered'}]")
    lines += [
        "",
        "## 4 · Divergences (structural change since analogue)",
    ]
    if mem.divergences:
        for div in mem.divergences:
            lines.append(f"- {div}")
    else:
        lines.append("- No structural divergence flagged — analogue transfer is clean.")
    lines += [
        "",
        f"## 5 · Trajectory (evolution engine)",
        f"- Now hour {ev['now_hour']} · 48h lookback review · 24h forecast",
        f"- Forecast peak **{ev['peak_probability']:.0%} @ hour {ev['peak_at_hour']}** "
        f"(Δ24h {ev['delta_24h'] * 100:+.0f}pp, {ev['trend']})",
        "",
        "## 6 · Verdict",
        f"- **{verdict['title']}**",
        f"- Recommendation: {verdict['advice']}",
        "",
        "_EarthPulse AI — engine-derived comparison; archived records are provenance-tagged "
        "synthetic signatures. Confidence bounds printed where material._",
    ]
    return "\n".join(lines)


def _beautify(items: list[str]) -> str:
    return "; ".join(items) if items else "none flagged"


def comparative_analysis(db, location_id: str) -> dict:
    loc = db.get(Location, location_id)
    if loc is None:
        raise ValueError(location_id)

    outputs, _ = build_agent_outputs(db, location_id)
    comps = outputs.get("risk_fusion", {}).get("components", {})
    pred = outputs.get("prediction", {})
    p = pred.get("risk_probability", 0.0)

    mem = memory_for(location_id, loc.hazard_type)
    matches = analogue_matches(location_id, comps, loc.hazard_type)

    analogues = []
    for m in matches:
        event = next((e for e in mem.events
                      if e.name == m["event"] and e.date == m["date"]), None)
        sig = event.signature if event else {}
        drivers = _driver_deltas(comps, sig, loc.hazard_type) if sig else []
        analogues.append({
            "event": m["event"], "date": m["date"], "severity": m["severity"],
            "similarity": m["similarity"], "description": m["description"],
            "drivers": drivers,
            "matching_drivers": sum(1 for d in drivers if d["matched"]),
            "reliability": _reliability(comps, sig, m["similarity"], mem.divergences, loc.hazard_type) if sig else "Low",
        })

    evdata = risk_evolution(db, loc, lookback_h=48, horizon_h=24)
    evdata["trend"] = _trend(evdata.get("delta_24h", 0))
    verdict = _verdict(analogues, evdata)

    past = (
        db.query(Prediction)
        .filter_by(location_id=location_id, event_type=loc.hazard_type)
        .order_by(Prediction.generated_at.desc()).limit(5).all()
    )
    previous = [{
        "generated_at": row.generated_at.isoformat(),
        "risk_probability": round(row.risk_probability, 3),
        "severity": round(row.severity, 3),
    } for row in past]

    return {
        "location_id": location_id,
        "location_name": loc.name,
        "region": loc.region,
        "hazard": loc.hazard_type,
        "live": {
            "hour": evdata["now_hour"],
            "risk_probability": round(p, 3),
            "level": levels_for(loc.hazard_type, p),
            "severity": round(pred.get("severity", 0), 2),
            "confidence": round(pred.get("confidence", 0), 2),
            "components": {k: round(v, 2) for k, v in comps.items()},
        },
        "historical": {
            "floods_10y": mem.floods_10y,
            "vulnerabilities": mem.vulnerabilities,
            "choke_points": mem.choke_points,
        },
        "analogues": analogues,
        "evolution": {
            "now_hour": evdata["now_hour"],
            "peak_probability": evdata["peak_probability"],
            "peak_at_hour": evdata["peak_at_hour"],
            "delta_24h": evdata["delta_24h"],
            "trend": evdata["trend"],
        },
        "previous_records": previous,
        "verdict": verdict,
        "markdown": _render_markdown(loc, comps, pred, analogues, evdata, mem, verdict,
                                     previous),
        "generated_at": datetime.now(timezone.utc),
    }