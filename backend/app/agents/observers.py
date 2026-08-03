"""Observer agents — Citizen Report and News Intelligence.

Ground truth and context signals. Both carry credibility weighting into fusion.
"""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent


class CitizenReportAgent(BaseAgent):
    name = "citizen_report"
    mission = "Cluster verified citizen reports into ground-truth pressure signals."
    inputs = ["citizen_reports"]
    outputs = ["citizen_pressure", "report_clusters"]
    failure_mode = "sparse reports → pressure floors low, confidence scales with report count"

    def run(self, ctx: AgentContext) -> AgentResult:
        reports = ctx.payload.get("citizen_reports") or []
        verified = [r for r in reports if r.get("verified")]
        weight = sum(1.5 if r.get("verified") else 0.6 for r in reports)
        pressure = min(8.0, weight / 1.2)
        confidence = min(0.9, 0.3 + 0.1 * len(reports))
        return AgentResult(
            outputs={"citizen_pressure": round(pressure, 2), "report_clusters": len(verified)},
            confidence=confidence,
            messages=[f"{len(reports)} reports, {len(verified)} verified → pressure {pressure:.2f}"],
            used_sources=[r["source_id"] for r in reports[-5:]],
        )


class NewsAgent(BaseAgent):
    name = "news"
    mission = "Surface official warnings and credible event mentions from news streams."
    inputs = ["news_items"]
    outputs = ["event_tags", "warning_level"]
    failure_mode = "no news → context neutral, do not infer events"

    def run(self, ctx: AgentContext) -> AgentResult:
        items = ctx.payload.get("news_items") or []
        if not items:
            return AgentResult(confidence=0.3, outputs={"event_tags": [], "warning_level": 0})
        credible = [i for i in items if i.get("credibility", 0.5) >= 0.6]
        tags = sorted({t for i in credible for t in i.get("tags", [])})
        warning = max((i.get("warning_level", 0) for i in credible), default=0)
        return AgentResult(
            outputs={"event_tags": tags, "warning_level": warning},
            confidence=min(0.85, 0.4 + 0.1 * len(credible)),
            used_sources=[i["source_id"] for i in credible[-4:]],
            messages=[f"{len(credible)} credible items; tags={tags}"],
        )
