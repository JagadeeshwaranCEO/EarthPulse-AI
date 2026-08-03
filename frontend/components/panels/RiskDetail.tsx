"use client";

import { useEffect, useState } from "react";
import { api, type AttributionItem, type Evidence, type ForecastPoint, type RiskDetail } from "@/lib/api";
import { Badge, Meter, Panel } from "@/components/ui/Panel";
import { ConfidenceMeter } from "@/components/viz/ConfidenceMeter";
import { ForecastChart } from "@/components/viz/ForecastChart";
import { TrustPill } from "@/components/ui/TrustPill";

const COMPONENT_LABELS: Record<string, string> = {
  rain_intensity: "rain intensity",
  soil_moisture: "soil moisture anomaly",
  headroom_deficit: "drainage headroom deficit",
  drainage_stress: "stormwater network stress",
  citizen_pressure: "verified ground reports",
  aq_anomaly: "air quality anomaly",
};

export function RiskDetail({ riskId }: { riskId: string }) {
  const [detail, setDetail] = useState<RiskDetail | null>(null);
  const [forecast, setForecast] = useState<{ points: ForecastPoint[]; probability_now: number } | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    api.risk(riskId).then((d) => alive && setDetail(d)).catch(() => {});
    api.prediction(riskId).then((f) => alive && setForecast(f)).catch(() => {});
    return () => { alive = false; };
  }, [riskId]);

  if (!detail || typeof detail.severity !== "number") {
    return <Panel title="risk detail"><p className="p-4 text-xs text-mono">loading telemetry…</p></Panel>;
  }

  return (
    <Panel
      title={`risk detail · ${detail.location_name}`}
      right={
        <div className="flex items-center gap-2">
          <TrustPill riskId={riskId} />
          <Badge tone={detail.level === "critical" ? "red" : detail.level === "high" ? "amber" : detail.level === "moderate" ? "blue" : "green"}>{detail.level}</Badge>
          <Badge tone={detail.llm_mode === "live" ? "green" : "slate"}>{detail.llm_mode === "live" ? "llm live" : "template reasoning"}</Badge>
        </div>
      }
    >
      <div className="space-y-4 p-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2 rounded border border-edge bg-panel2 p-3">
            <ConfidenceMeter confidence={detail.confidence} />
            <div className="telemetry text-[10px] text-mono">
              model: {detail.model_name}
              <br />horizon: {detail.horizon_h}h · sev {detail.severity.toFixed(1)}/5
            </div>
          </div>
          <div className="space-y-2 rounded border border-edge bg-panel2 p-3">
            {Object.entries(detail.components).filter(([k]) => k in COMPONENT_LABELS).slice(0, 4).map(([k, v]) => (
              <Meter key={k} label={COMPONENT_LABELS[k]} value={v} max={12} color={v > 9 ? "#EF4444" : v > 6 ? "#F59E0B" : "#3B82F6"} />
            ))}
          </div>
        </div>

        {forecast && (
          <div className="rounded border border-edge bg-panel2 p-2">
            <div className="mb-1 flex justify-between px-1">
              <span className="telemetry text-[10px] uppercase tracking-widest text-mono">24h forecast · uncertainty band</span>
              <span className="telemetry text-[10px] text-accent-blue">peak {(Math.max(...forecast.points.map((p) => p.mean)) * 100).toFixed(0)}%</span>
            </div>
            <ForecastChart points={forecast.points} now={detail.risk_probability} />
          </div>
        )}

        <div>
          <div className="mb-1.5 telemetry text-[10px] uppercase tracking-widest text-mono">feature attribution · SHAP pane</div>
          <AttributionPane items={detail.attribution} />
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="telemetry text-[10px] uppercase tracking-widest text-mono">evidence & provenance ({detail.evidence.length})</span>
            <button onClick={() => setEvidenceOpen((v) => !v)} className="telemetry text-[10px] text-accent-blue">{evidenceOpen ? "collapse" : "expand"}</button>
          </div>
          {evidenceOpen && <EvidencePane evidence={detail.evidence} />}
        </div>

        <div className="rounded border border-accent-amber/40 bg-accent-amber/5 p-2.5">
          <span className="telemetry text-[10px] uppercase tracking-widest text-accent-amber">known limitations</span>
          <ul className="mt-1 space-y-0.5 text-[11px] text-slate-300">
            {detail.limitations.map((l, i) => <li key={i}>· {l}</li>)}
          </ul>
        </div>
      </div>
    </Panel>
  );
}

function AttributionPane({ items }: { items: AttributionItem[] }) {
  const max = Math.max(1, ...items.map((i) => i.influence));
  return (
    <div className="space-y-1.5">
      {items.map((a) => (
        <div key={a.feature} className="flex items-center gap-2">
          <span className="w-40 shrink-0 truncate text-[11px] text-slate-300">{a.feature.replace(/_/g, " ")}</span>
          <div className="h-2 flex-1 overflow-hidden rounded bg-panel2">
            <div className={`h-full rounded transition-all duration-500 ${a.direction === "raises" ? "bg-accent-red" : "bg-accent-green"}`} style={{ width: `${(a.influence / max) * 100}%` }} />
          </div>
          <span className="telemetry w-10 text-right text-[10px] text-mono">{(a.influence * 100).toFixed(0)}%</span>
          <span className={`telemetry w-12 text-right text-[9px] ${a.direction === "raises" ? "text-accent-red" : "text-accent-green"}`}>{a.direction}</span>
        </div>
      ))}
    </div>
  );
}

function EvidencePane({ evidence }: { evidence: Evidence[] }) {
  return (
    <div className="space-y-1.5">
      {evidence.map((e) => (
        <div key={e.id} className="rounded border border-edge bg-panel2 p-2">
          <div className="flex items-center justify-between">
            <Badge tone="blue">{e.kind}</Badge>
            <span className="telemetry text-[9px] text-mono">{e.captured_at.slice(0, 16).replace("T", " ")}</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-300">{e.description}</p>
          <div className="mt-1 flex items-center justify-between">
            {e.value != null && <span className="telemetry text-[10px] text-mono">value {e.value}</span>}
            <span className="telemetry truncate text-[9px] text-mono/70">
              {e.provenance.source_name}{e.provenance.is_synthetic ? " · synthetic" : ""}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
