"use client";

import { useEffect, useState } from "react";
import { api, type ReliabilityRow, type ValidationReport } from "@/lib/api";
import { Badge, Panel } from "@/components/ui/Panel";

export function ValidationPanel() {
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.validation()
      .then((r) => alive && setReport(r))
      .catch(() => alive && setError("validation endpoint unreachable"));
    return () => { alive = false; };
  }, []);

  if (error) return <Panel title="validation · precision report card"><p className="p-4 text-xs text-accent-red">{error}</p></Panel>;

  return (
    <Panel title="validation · computed precision report card">
      <div className="space-y-4 p-3">
        {!report && <p className="text-xs text-mono">computing rolling holdout over the seed arc…</p>}

        {report && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="slate">{report.scope}</Badge>
              <span className="telemetry text-[10px] text-mono">{report.method}</span>
              <span className="telemetry text-[10px] text-mono">samples {report.overall.samples} · zones {report.overall.zones}</span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <Stat label="brier" value={report.overall.brier.toFixed(3)} />
              <Stat label="skill vs climatology" value={report.overall.brier_skill.toFixed(2)} tone={report.overall.brier_skill >= 0.3 ? "green" : report.overall.brier_skill >= 0 ? "blue" : "red"} />
              <Stat label="roc auc" value={report.overall.auc == null ? "—" : report.overall.auc.toFixed(2)} />
              <Stat label="sharpness (band)" value={report.overall.sharpness.toFixed(3)} />
              <Stat label="mean forecast" value={(report.overall.calibration.mean_forecast * 100).toFixed(0) + "%"} />
              <Stat label="gap" value={(report.overall.calibration.gap * 100).toFixed(0) + "%"} tone={report.overall.calibration.sign} />
            </div>

            <div>
              <div className="mb-1.5 telemetry text-[10px] uppercase tracking-widest text-mono">reliability · forecast decile vs observed</div>
              <ReliabilityTable rows={report.overall.reliability} />
            </div>

            <div>
              <div className="mb-1.5 telemetry text-[10px] uppercase tracking-widest text-mono">zone precision tiers</div>
              <div className="space-y-1">
                {report.zones.map((z) => (
                  <div key={z.location_id} className="flex items-center justify-between rounded border border-edge bg-panel1 px-2 py-1">
                    <span className="truncate text-[11px] text-slate-300">{z.location_name}</span>
                    <span className="flex items-center gap-2">
                      <span className="telemetry text-[9px] text-mono">brier {z.brier.toFixed(3)} · skill {z.brier_skill.toFixed(2)}</span>
                      <Badge tone={z.tier === "A" ? "green" : z.tier === "B" ? "blue" : "slate"}>{z.tier}</Badge>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  const color = tone === "green" ? "text-accent-green" : tone === "red" ? "text-accent-red" : tone === "blue" ? "text-accent-blue" : tone === "under-forecast" ? "text-accent-red" : tone === "over-forecast" ? "text-accent-amber" : "text-slate-300";
  return (
    <div className="rounded border border-edge bg-panel2 px-2.5 py-2">
      <div className={`telemetry text-[15px] ${color}`}>{value}</div>
      <div className="telemetry text-[9px] uppercase tracking-wider text-mono">{label}</div>
    </div>
  );
}

function ReliabilityTable({ rows }: { rows: ReliabilityRow[] }) {
  return (
    <div className="space-y-1">
      {rows.map((r) => (
        <div key={r.band} className="flex items-center gap-2">
          <span className="telemetry w-16 shrink-0 text-right text-[9px] text-mono">{r.band}</span>
          <div className="h-2.5 flex-1 overflow-hidden rounded bg-panel2">
            <div className="flex h-full">
              <div className="bg-accent-blue" style={{ width: `${Math.min(100, r.mean_forecast * 100)}%` }} />
              <div className="h-full w-px bg-white/40" />
              <div className="bg-accent-amber" style={{ width: `${Math.min(100, Math.max(0, r.observed_fraction * 100 - r.mean_forecast * 100))}%` }} />
            </div>
          </div>
          <span className="telemetry w-8 shrink-0 text-[9px] text-mono">n={r.forecasts}</span>
        </div>
      ))}
    </div>
  );
}