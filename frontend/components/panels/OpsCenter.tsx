"use client";

import { useEffect, useState } from "react";
import { Badge, Panel } from "@/components/ui/Panel";

interface OpsSummary {
  theatre: string;
  ghost_enabled: boolean;
  sms_enabled: boolean;
  push_enabled: boolean;
  alerts_24h: number;
  active_alerts: number;
  field_reports: number;
  field_confirmed: number;
  field_pending: number;
  scenarios: number;
  ghost_actions: number;
  sms_recipients: number;
  sms_messages: number;
  sms_sent: number;
}

interface OpsEvent {
  kind: string;
  at: string;
  zone: string;
  level: string;
  detail: string;
}

const KIND_TONE: Record<string, "red" | "amber" | "blue" | "green" | "slate"> = {
  alert: "red",
  field_report: "amber",
  scenario: "blue",
  sms: "green",
  ghost: "slate",
};

function Stat({ label, value, tone = "text-slate-100" }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="rounded border border-edge bg-panel1 px-2.5 py-2">
      <div className={`telemetry text-lg font-semibold ${tone}`}>{value}</div>
      <div className="telemetry text-[9px] uppercase tracking-widest text-mono">{label}</div>
    </div>
  );
}

export function OpsCenter() {
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [events, setEvents] = useState<OpsEvent[]>([]);
  const [toggling, setToggling] = useState(false);

  const load = () => {
    fetch("/api/v1/ops/summary").then((r) => r.json()).then(setSummary).catch(() => {});
    fetch("/api/v1/ops/events?limit=30").then((r) => r.json()).then(setEvents).catch(() => {});
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  const toggleGhost = async () => {
    setToggling(true);
    try {
      const res = await fetch("/api/v1/ops/ghost/toggle", { method: "POST" });
      const d = await res.json();
      setSummary((s) => (s ? { ...s, ghost_enabled: d.ghost_enabled } : s));
    } finally {
      setToggling(false);
    }
  };

  return (
    <Panel
      title="live ops center · heads-up"
      right={
        summary ? (
          <span className="telemetry flex items-center gap-2 text-[9px] uppercase tracking-widest text-mono">
            <Badge tone={summary.ghost_enabled ? "red" : "slate"}>{summary.ghost_enabled ? "ghost armed" : "ghost off"}</Badge>
            <Badge tone={summary.sms_enabled ? "green" : "slate"}>{summary.sms_enabled ? "sms on" : "sms off"}</Badge>
            <Badge tone={summary.push_enabled ? "blue" : "slate"}>{summary.push_enabled ? "push on" : "push off"}</Badge>
          </span>
        ) : undefined
      }
    >
      <div className="space-y-3 p-3">
        {!summary && <p className="text-xs text-mono">reading the floor…</p>}

        {summary && (
          <>
            <div className="grid grid-cols-4 gap-2">
              <Stat label="alerts 24h" value={summary.alerts_24h} tone={summary.alerts_24h > 0 ? "text-accent-red" : "text-slate-100"} />
              <Stat label="active alerts" value={summary.active_alerts} tone={summary.active_alerts > 0 ? "text-accent-amber" : "text-slate-100"} />
              <Stat label="field reports" value={summary.field_reports} />
              <Stat label="scenarios" value={summary.scenarios} tone="text-accent-blue" />
              <Stat label="sms sent" value={summary.sms_sent} tone="text-accent-green" />
              <Stat label="sms recipients" value={summary.sms_recipients} />
              <Stat label="ghost actions" value={summary.ghost_actions} />
              <Stat label="theatre" value={summary.theatre} />
            </div>

            <button
              onClick={toggleGhost} disabled={toggling}
              className={`w-full rounded border py-2 text-[12px] font-semibold transition-colors disabled:opacity-40 ${
                summary.ghost_enabled
                  ? "border-accent-red/60 bg-accent-red/10 text-accent-red hover:bg-accent-red/20"
                  : "border-accent-blue/60 bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20"
              }`}
            >
              {toggling ? "flipping…" : summary.ghost_enabled ? "disarm ghost mode" : "arm ghost mode"}
            </button>

            <div>
              <div className="telemetry mb-1.5 flex items-center gap-2 text-[10px] uppercase tracking-widest text-mono">
                <span className="text-accent-blue">event feed</span>
                <span className="h-px flex-1 bg-edge" />
              </div>
              <div className="space-y-1.5">
                {events.length === 0 && <p className="text-[10px] text-mono">no events yet — run a scenario or submit a field report</p>}
                {events.map((e, i) => (
                  <div key={i} className="flex items-start gap-2 rounded border border-edge bg-panel1 px-2.5 py-1.5">
                    <Badge tone={KIND_TONE[e.kind] ?? "slate"}>{e.kind}</Badge>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[10px] text-slate-300">{e.detail}</p>
                      <p className="telemetry text-[9px] text-mono">{e.zone} · {e.level} · {e.at.slice(0, 19).replace("T", " ")}</p>
                    </div>
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
