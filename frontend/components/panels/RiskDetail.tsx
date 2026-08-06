"use client";

import { useEffect, useState } from "react";
import { api, type AttributionItem, type Evidence, type LeadRung, type PredictionResponse, type RiskDetail } from "@/lib/api";
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
  const [forecast, setForecast] = useState<PredictionResponse | null>(null);
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
              <span className="telemetry text-[10px] text-accent-blue">peak {(forecast.peak_probability * 100).toFixed(0)}% in +{forecast.peak_in_h}h</span>
            </div>
            <ForecastChart points={forecast.points} now={detail.risk_probability} />
            {forecast.lead_ladder?.length > 0 && (
              <div className="mt-2">
                <span className="telemetry px-1 text-[10px] uppercase tracking-widest text-mono">lead ladder · forward-signal nowcast</span>
                <LeadLadder ladders={forecast.lead_ladder} />
              </div>
            )}
          </div>
        )}

        {detail.precision && (
          <div className="rounded border border-edge bg-panel2 p-2.5">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="telemetry text-[10px] uppercase tracking-widest text-mono">verified precision · rolling holdout</span>
              <Badge tone={detail.precision.tier === "A" ? "green" : detail.precision.tier === "B" ? "blue" : "slate"}>tier {detail.precision.tier}</Badge>
            </div>
            <div className="grid grid-cols-3 gap-1.5 text-center">
              <Metric label="brier" value={detail.precision.brier.toFixed(3)} />
              <Metric label="skill vs clim" value={detail.precision.brier_skill.toFixed(2)} />
              <Metric label="calibration gap" value={detail.precision.calibration ? detail.precision.calibration.gap.toFixed(2) : "—"} accent={detail.precision.calibration?.sign} />
            </div>
          </div>
        )}

        {detail.crossing?.high_band && (
          <div className="rounded border border-edge bg-panel2 p-2.5">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="telemetry text-[10px] uppercase tracking-widest text-mono">threshold crossings · if trajectory holds</span>
              <span className="telemetry text-[9px] text-mono/70">{detail.crossing.method}</span>
            </div>
            <div className="space-y-1 text-[11px] text-slate-300">
              {detail.crossing.high_band && <p>high band (&gt;{(detail.crossing.high_band.threshold * 100).toFixed(0)}%): <span className="text-accent-amber">{detail.crossing.high_band.crossing_in_h === null ? "not in 72h window" : `~${detail.crossing.high_band.crossing_in_h}h`}</span></p>}
              {detail.crossing.moderate_band && <p>moderate band (&gt;{(detail.crossing.moderate_band.threshold * 100).toFixed(0)}%): <span className="text-accent-blue">{detail.crossing.moderate_band.crossing_in_h === null ? "not in 72h window" : `~${detail.crossing.moderate_band.crossing_in_h}h`}</span></p>}
            </div>
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

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  const tone = accent === "under-forecast" ? "text-accent-red" : accent === "over-forecast" ? "text-accent-amber" : "text-slate-300";
  return (
    <div className="rounded bg-panel1 px-2 py-1.5">
      <div className={`telemetry text-[12px] ${tone}`}>{value}</div>
      <div className="telemetry text-[9px] uppercase tracking-wider text-mono">{label}</div>
    </div>
  );
}

function LeadLadder({ ladders }: { ladders: LeadRung[] }) {
  return (
    <div className="mt-1 flex gap-1.5">
      {ladders.map((r) => (
        <div key={r.lead_h} className="flex-1 rounded border border-edge bg-panel1 p-1.5 text-center">
          <div className="telemetry text-[9px] uppercase text-mono">+{r.lead_h}h</div>
          <div className="telemetry text-[12px]" style={{ color: r.probability > 0.5 ? "#F59E0B" : r.probability > 0.25 ? "#3B82F6" : "#64748B" }}>{(r.probability * 100).toFixed(0)}%</div>
          <div className="telemetry text-[9px] text-mono/70">{r.level}</div>
          <div className="mt-0.5 flex h-1 overflow-hidden rounded bg-panel2">
            <div className="bg-accent-blue transition-all duration-500" style={{ width: `${r.probability * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
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
