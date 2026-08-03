"use client";

import { levelColor, levelFill, type RiskSummary } from "@/lib/api";

export function RiskList({ risks, selectedId, onSelect }: { risks: RiskSummary[]; selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <div className="divide-y divide-edge">
      {risks.map((r) => (
        <button
          key={r.location_id}
          onClick={() => onSelect(r.location_id)}
          className={`flex w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-panel2 ${selectedId === r.location_id ? "bg-panel2" : ""}`}
        >
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: levelFill(r.level) }} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-[12px] font-medium text-slate-200">{r.location_name}</span>
              <span className={`telemetry shrink-0 text-[11px] font-semibold ${levelColor(r.level)}`}>{(r.risk_probability * 100).toFixed(0)}%</span>
            </div>
            <div className="mt-0.5 flex items-center justify-between">
              <span className={`telemetry text-[10px] ${r.trend === "rising" ? "text-accent-red" : "text-mono"}`}>
                {r.trend} {r.trend === "rising" ? "↗" : "→"} · {r.event_type}
              </span>
              <span className="telemetry text-[10px] text-mono">conf {(r.confidence * 100).toFixed(0)}% · sev {r.severity.toFixed(1)}</span>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
