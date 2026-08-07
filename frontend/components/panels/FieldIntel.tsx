"use client";

import { useEffect, useState } from "react";
import { Badge, Panel } from "@/components/ui/Panel";

interface FieldReport {
  id: number;
  location_id: string | null;
  location_name: string | null;
  hazard_type: string;
  observed_severity: number;
  description: string;
  distance_km: number;
  agreement: number;
  status: "pending" | "confirmed" | "dismissed";
  medium: string;
  reporter: string | null;
  votes: number;
  flagged: boolean;
  created_at: string;
}

interface ZoneStat {
  location_id: string;
  location_name: string;
  reports: number;
  confirmed: number;
  avg_severity: number;
  avg_agreement: number;
}

interface Summary {
  total: number;
  confirmed: number;
  pending: number;
  dismissed: number;
  flagged: number;
  zones: ZoneStat[];
}

const STATUS_TONE: Record<string, "red" | "amber" | "blue" | "green" | "slate"> = {
  confirmed: "green",
  pending: "amber",
  dismissed: "red",
};

export function FieldIntel() {
  const [reports, setReports] = useState<FieldReport[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [severity, setSeverity] = useState(3);
  const [desc, setDesc] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    fetch("/api/v1/field/summary").then((r) => r.json()).then(setSummary).catch(() => {});
    fetch("/api/v1/field/reports?limit=25").then((r) => r.json()).then(setReports).catch(() => {});
  };

  useEffect(() => {
    load();
  }, []);

  const submit = async () => {
    if (desc.trim().length < 3) return;
    setSubmitting(true);
    try {
      await fetch("/api/v1/field/reports", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          hazard_type: "flood",
          observed_severity: severity,
          description: desc,
          lat: 13.0827,
          lon: 80.2707,
          medium: "web",
        }),
      });
      setDesc("");
      load();
    } finally {
      setSubmitting(false);
    }
  };

  const act = async (id: number, action: "vote" | "confirmed" | "dismissed") => {
    const init: RequestInit =
      action === "vote"
        ? { method: "POST" }
        : { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ status: action }) };
    await fetch(`/api/v1/field/reports/${id}/${action === "vote" ? "vote" : "status"}`, init).catch(() => {});
    load();
  };

  return (
    <Panel
      title="field intel · ground truth loop"
      right={summary ? <Badge tone={summary.flagged > 0 ? "red" : summary.pending > 0 ? "amber" : "green"}>{summary.total} reports</Badge> : undefined}
    >
      <div className="space-y-3 p-3">
        <div className="rounded border border-edge bg-panel1 p-2.5">
          <div className="telemetry text-[9px] uppercase tracking-widest text-mono">new report</div>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {[0, 1, 2, 3, 4, 5].map((s) => (
              <button
                key={s}
                onClick={() => setSeverity(s)}
                className={`rounded border px-2 py-0.5 text-[10px] transition-colors ${
                  severity === s ? "border-accent-amber/60 bg-accent-amber/15 text-accent-amber" : "border-edge text-mono hover:bg-panel2"
                }`}
              >
                {s}
              </button>
            ))}
            <span className="telemetry text-[9px] text-mono">severity {severity}/5</span>
          </div>
          <input
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="what are people seeing on the ground?"
            className="mt-2 w-full rounded border border-edge bg-panel px-2 py-1.5 text-[11px] text-slate-200 placeholder:text-mono/60 focus:border-accent-blue focus:outline-none"
          />
          <button
            onClick={submit}
            disabled={submitting || desc.trim().length < 3}
            className="mt-2 w-full rounded border border-accent-blue/60 bg-accent-blue/10 py-1.5 text-[11px] font-semibold text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting ? "submitting…" : "submit field report"}
          </button>
        </div>

        {reports.length > 0 && (
          <div className="space-y-1.5">
            <div className="telemetry flex items-center gap-2 text-[10px] uppercase tracking-widest text-mono">
              <span className="text-accent-blue">latest reports</span>
              <span className="h-px flex-1 bg-edge" />
              <span>{reports.length}</span>
            </div>
            {reports.map((r) => (
              <div key={r.id} className="rounded border border-edge bg-panel1 px-2.5 py-2">
                <div className="flex items-center gap-2">
                  <Badge tone={STATUS_TONE[r.status] ?? "slate"}>{r.status}</Badge>
                  <span className="truncate text-[10px] font-medium text-slate-300">{r.location_name ?? "unbound"}</span>
                  <span className="telemetry ml-auto text-[9px] text-mono">{r.created_at.slice(0, 19).replace("T", " ")}</span>
                </div>
                <p className="mt-1 text-[10px] leading-relaxed text-slate-300">{r.description}</p>
                <div className="mt-1.5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button onClick={() => act(r.id, "vote")} className="telemetry rounded border border-edge px-1.5 py-0.5 text-[9px] text-slate-300 hover:bg-panel2">
                      +{r.votes} vote
                    </button>
                    {r.status !== "confirmed" && (
                      <button onClick={() => act(r.id, "confirmed")} className="telemetry rounded border border-accent-green/50 px-1.5 py-0.5 text-[9px] text-accent-green hover:bg-accent-green/10">
                        confirm
                      </button>
                    )}
                    {r.status !== "dismissed" && (
                      <button onClick={() => act(r.id, "dismissed")} className="telemetry rounded border border-accent-red/50 px-1.5 py-0.5 text-[9px] text-accent-red hover:bg-accent-red/10">
                        dismiss
                      </button>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {r.flagged && <Badge tone="red">flagged</Badge>}
                    <span className="telemetry text-[9px] text-mono">agreement {Math.round(r.agreement * 100)}%</span>
                    <span className="telemetry text-[9px] text-mono">sev {r.observed_severity}/5</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {summary?.zones.length ? (
          <div className="space-y-1.5">
            <div className="telemetry flex items-center gap-2 text-[10px] uppercase tracking-widest text-mono">
              <span className="text-accent-blue">calibration by zone</span>
              <span className="h-px flex-1 bg-edge" />
            </div>
            {summary.zones.map((z) => (
              <div key={z.location_id} className="rounded border border-edge bg-panel1 px-2.5 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-medium text-slate-300">{z.location_name}</span>
                  <span className="telemetry text-[9px] text-mono">{z.reports} reports · {z.confirmed} confirmed</span>
                </div>
                <div className="mt-1.5 flex items-center gap-2">
                  <span className="telemetry w-20 shrink-0 text-[9px] text-mono">agreement</span>
                  <div className="h-1.5 w-full overflow-hidden rounded bg-panel">
                    <div className="h-full rounded bg-accent-blue transition-all duration-700" style={{ width: `${z.avg_agreement * 100}%` }} />
                  </div>
                  <span className="telemetry w-8 shrink-0 text-right text-[10px] text-slate-300">{Math.round(z.avg_agreement * 100)}%</span>
                </div>
                <div className="mt-1 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="telemetry text-[9px] text-mono">avg severity</span>
                    <span className="text-[10px] text-slate-300">{z.avg_severity}/5</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {summary && (
          <div className="telemetry flex flex-wrap gap-3 border-t border-edge pt-2 text-[9px] uppercase tracking-widest text-mono">
            <span>{summary.total} total</span>
            <span className="text-accent-green">{summary.confirmed} confirmed</span>
            <span className="text-accent-amber">{summary.pending} pending</span>
            <span className="text-accent-red">{summary.dismissed} dismissed</span>
            <span>{summary.flagged} flagged</span>
          </div>
        )}
      </div>
    </Panel>
  );
}