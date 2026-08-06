"""EarthPulse Mission Brief — the decision layer's operator artifact.

Composes a stakeholder-ready brief from the recommended optimization strategy,
decision robustness analysis, environmental memory + evolution arc, and the top
live risks. Every number is produced by the underlying engines (optimizer,
analysis, memory, evolution); each section carries a confidence/provenance note
— no fabricated claims.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.decision_optimizer import StrategyOption


def _level(p: float) -> str:
    return "critical" if p >= 0.75 else "high" if p >= 0.55 else "moderate" if p >= 0.3 else "low"


def build_mission_brief(
    *,
    strategy: StrategyOption,
    top_risks: list[dict],
    peak_risk: float,
    peak_at_hour: int,
    now_hour: int,
    memory_line: str | None = None,
    analysis: dict | None = None,
    trust: dict | None = None,
) -> dict:
    """Assemble the full brief (markdown text + structured facets)."""
    analysis = analysis or {}
    trust = trust or {}
    trade_offs = analysis.get("trade_offs", {})
    decision_conf = analysis.get("decision_confidence")
    robustness = analysis.get("robustness_rainfall_pct")
    fallback_id = analysis.get("fallback_strategy_id") or ""
    fallback_trigger = analysis.get("fallback_trigger")
    timeline = strategy.execution_timeline or []

    lines = [
        f"# EarthPulse Mission Brief — {strategy.title}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ·  "
        f"Sim clock hour {now_hour}  ·  Peak {peak_risk:.0%} around hour {peak_at_hour}",
        "",
        "## 1 · Situation",
    ]
    for r in top_risks[:5]:
        lines.append(
            f"- **{r['location_name']}** — risk {r['risk_probability']:.0%} "
            f"({_level(r['risk_probability'])}), severity {r['severity']:.1f}/5, "
            f"confidence {r['confidence']:.0%}"
        )
    lines.extend(
        [
            "",
            "## 2 · What memory tells us",
            f"- {memory_line or 'No strong historical analogue for current telemetry.'}",
            "",
            "## 3 · Data trust",
        ]
    )
    if trust:
        lines.append(
            f"- **Data trust: {trust.get('level', '—')}** ({trust.get('score', 0):.0f}/100) — "
            f"separates operational trust in sensors from mathematical confidence."
        )
        for c in trust.get("checks", [])[:5]:
            mark = "✓" if c.get("ok") else "✗"
            lines.append(f"- {mark} {c.get('label', '')} — {c.get('detail', '')}")
        lines.append(
            f"- Prediction confidence: {analysis.get('prediction_confidence', 0):.0%} · "
            f"robust to +{robustness}% rainfall variance."
        )
    else:
        lines.append("- Data trust: unknown (no telemetry state).")
    lines.extend(
        [
            "",
            "## 4 · Decision confidence",
        ]
    )
    if decision_conf is not None:
        lines.append(
            f"- **Decision confidence: {decision_conf:.0%}** — probability the selected plan "
            f"remains optimal under precipitation variance."
        )
        if fallback_id:
            lines.append(f"- If forecast degrades: **switch to {fallback_id}** ({fallback_trigger}).")
        else:
            lines.append("- No strategy switch required across the {0.85–1.60}× variance sweep.")
    else:
        lines.append(f"- Strategy confidence: {strategy.confidence_score:.0%}")
    lines.extend(
        [
            "",
            "## 5 · Why this plan (trade-off matrix)",
        ]
    )
    for sid, meta in trade_offs.items():
        sel = "→ selected" if sid == strategy.id else ""
        lines.append(
            f"- **{sid.replace('strat_', 'Strategy ').title()}** {sel} — "
            f"{meta['objective']}. Trade-off: {meta['trade_off']}"
        )
    lines.extend(
        [
            "",
            "## 6 · Recommended allocations",
        ]
    )
    for unit in ("boat", "pump", "shelter"):
        alloc = strategy.allocations.get(unit, {})
        active = [(zid, cnt) for zid, cnt in alloc.items() if cnt > 0]
        if active:
            detail = ", ".join(f"{count}× {zid}" for zid, count in sorted(active, key=lambda kv: -kv[1])[:5])
            lines.append(f"- **{unit.capitalize()}**: {detail}")
    lines.append(f"- **Focus**: {strategy.focus} · strategy confidence {strategy.confidence_score:.0%}")
    lines.extend(
        [
            "",
            "## 7 · Execution timeline",
        ]
    )
    if timeline:
        for step in timeline:
            lines.append(f"- **{step['time']}** ({step['label']}) · {step['phase']} — {step['action']}")
    else:
        lines.append("- No timeline available.")
    lines.extend(
        [
            "",
            "## 8 · Expected impact (model-based estimate)",
            f"- Lives protected: **{strategy.lives_protected:,}**",
            f"- Residual economic exposure: **₹{strategy.economic_loss_inr_cr:.1f} crore**",
            f"- Carbon avoided: **{strategy.co2_reduction_pct:.0f}%** via coordinated routing",
            "",
            "## 9 · Actions",
        ]
    )
    for a in strategy.actions:
        lines.append(f"- {a}")
    lines.append("")
    lines.append(
        "_EarthPulse AI · simulation-informed, not predicted-by-LLM. Confidence bounds "
        "and synthetic-data provenance printed per figure where material._"
    )

    return {
        "strategy_id": strategy.id,
        "title": strategy.title,
        "recommended": strategy.is_recommended,
        "markdown": "\n".join(lines),
        "facets": {
            "situation": [
                {"name": r["location_name"], "p": r["risk_probability"], "level": r["level"]} for r in top_risks[:5]
            ],
            "decision": {
                "decision_confidence": decision_conf,
                "prediction_confidence": analysis.get("prediction_confidence"),
                "robustness_rainfall_pct": robustness,
                "fallback_strategy_id": fallback_id,
                "fallback_trigger": fallback_trigger,
            },
            "trust": {
                "level": trust.get("level"),
                "score": trust.get("score"),
                "checks": [{"label": c.get("label"), "ok": c.get("ok")} for c in trust.get("checks", [])],
            },
            "timeline": timeline,
            "impact_estimate": {
                "lives_protected": strategy.lives_protected,
                "residual_economic_exposure_inr_cr": strategy.economic_loss_inr_cr,
                "co2_reduction_pct": strategy.co2_reduction_pct,
            },
            "memory": memory_line,
            "provenance": "synthetic demo data; instruments as cited in source feed",
        },
        "generated_at": datetime.now(timezone.utc),
    }
