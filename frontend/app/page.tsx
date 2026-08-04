"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useMissionControl } from "@/hooks/useMissionControl";
import { levelFill, type RiskDetail } from "@/lib/api";
import { Panel, Tabs, Badge } from "@/components/ui/Panel";
import { PulseGauge } from "@/components/viz/PulseGauge";
import { TimeScrubber } from "@/components/viz/TimeScrubber";
import { RiskList } from "@/components/panels/RiskList";
import { RiskDetail as RiskDetailPanel } from "@/components/panels/RiskDetail";
import { CausalChain } from "@/components/panels/CausalChain";
import { SimulationSandbox } from "@/components/panels/SimulationSandbox";
import { DebatePanel } from "@/components/panels/DebatePanel";
import { Copilot } from "@/components/panels/Copilot";
import { MemoryPanel } from "@/components/panels/MemoryPanel";
import { DecisionPanel } from "@/components/panels/DecisionPanel";
import { ValidationPanel } from "@/components/panels/ValidationPanel";
import { CrisisBanner } from "@/components/ui/CrisisBanner";

const MapView = dynamic(() => import("@/components/map/MapView").then((m) => m.MapView), { ssr: false, loading: () => <div className="h-full w-full bg-panel" /> });
import { SearchBar } from "@/components/map/SearchBar";

function EmptyPanel({ label }: { label: string }) {
  return (
    <Panel title="risk detail">
      <p className="p-4 text-xs text-mono">{label}</p>
    </Panel>
  );
}

const TABS = [
  { id: "detail", label: "Detail" },
  { id: "causal", label: "Causal" },
  { id: "memory", label: "Memory" },
  { id: "decide", label: "Decide" },
  { id: "simulate", label: "Simulate" },
  { id: "agents", label: "Agents" },
  { id: "copilot", label: "Copilot" },
  { id: "validation", label: "Validation" },
];

const THEATRES: { id: string; label: string; cmd: string }[] = [
  { id: "chennai", label: "chennai", cmd: "chennai flood command" },
  { id: "tamilnadu", label: "tamil nadu", cmd: "tamil nadu state command" },
  { id: "india", label: "india", cmd: "all-india command" },
  { id: "wildfire", label: "california", cmd: "california wildfire command" },
  { id: "asia", label: "asia", cmd: "asia continent command" },
];

export default function MissionControl() {
  const { dash, wsLive, clock, scrub } = useMissionControl();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState("detail");
  const [risk, setRisk] = useState<RiskDetail | null>(null);

  useEffect(() => {
    if (!dash) return;
    setSelectedId((cur) => cur ?? dash.risks[0]?.location_id ?? null);
  }, [dash]);

  useEffect(() => {
    if (!selectedId) return;
    fetch(`/api/v1/risks/${selectedId}`).then((r) => r.json()).then(setRisk).catch(() => {});
  }, [selectedId]);

  const selectedRisk = dash?.risks.find((r) => r.location_id === selectedId);
  const crisis = dash?.crisis ?? false;

  return (
    <div className={`flex h-screen flex-col ${crisis ? "shadow-crisis" : ""}`} style={crisis ? { background: "radial-gradient(ellipse at top, rgba(239,68,68,0.14), transparent 60%), #0A0E14" } : undefined}>
      <CrisisBanner crisis={crisis} alertCount={dash?.alerts.length ?? 0} />

      <header className="flex items-center gap-4 border-b border-edge px-4 py-2">
        <div>
          <h1 className="text-[15px] font-bold tracking-wide text-slate-100">
            EARTHPULSE<span className="text-accent-blue"> AI</span>
          </h1>
          <p className="telemetry text-[9px] uppercase tracking-widest text-mono">planetary early warning intelligence · {THEATRES.find((t) => t.id === dash?.scope)?.cmd ?? "chennai flood command"}</p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <Badge tone={wsLive ? "green" : "slate"}>{wsLive ? "live telemetry" : "connecting…"}</Badge>
          <Badge tone="slate">{THEATRES.find((t) => t.id === dash?.scope)?.label ?? "chennai"} · theatre</Badge>
          <div className="flex items-center gap-1 rounded border border-edge p-0.5">
            {THEATRES.map((t) => (
              <button
                key={t.id}
                onClick={async () => {
                  if (t.id === dash?.scope) return;
                  await fetch("/api/v1/scope", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ scope: t.id }),
                  });
                  window.location.reload();
                }}
                className={`telemetry rounded px-2 py-0.5 text-[9px] uppercase tracking-widest ${dash?.scope === t.id ? "bg-accent-blue/25 text-accent-blue" : "text-mono hover:bg-panel2"}`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="telemetry text-[10px] text-mono">{dash?.time?.slice(0, 19).replace("T", " ") ?? "—"}</div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* LEFT RAIL */}
        <aside className="flex w-[300px] shrink-0 flex-col gap-3 border-r border-edge p-3">
          {dash && <PulseGauge score={dash.pulse.score} band={dash.pulse.band} />}
          <Panel title="active risks" className="min-h-0 flex-1">
            <RiskList risks={dash?.risks ?? []} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setTab("detail"); }} />
          </Panel>
          <Panel title="sim time">
            <div className="p-3">
              <TimeScrubber hour={clock?.hour ?? 48} max={clock?.max ?? 80} onScrub={scrub} running={wsLive} />
            </div>
          </Panel>
        </aside>

        {/* CENTER MAP */}
        <main className="relative min-w-0 flex-1 border-r border-edge">
          <MapView risks={dash?.risks ?? []} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setTab("detail"); }} />
          <SearchBar risks={dash?.risks ?? []} onSelect={(id) => { setSelectedId(id); setTab("detail"); }} />
          <div className="pointer-events-none absolute left-3 top-3 space-y-1.5">
            <div className="rounded border border-edge bg-panel/90 px-2.5 py-1.5 backdrop-blur-sm">
              <div className="telemetry text-[9px] uppercase tracking-widest text-mono">legend · flood risk</div>
              <div className="mt-1 flex gap-2">
                {[["critical", "#EF4444"], ["high", "#F59E0B"], ["moderate", "#3B82F6"], ["low", "#10B981"]].map(([l, c]) => (
                  <span key={l} className="flex items-center gap-1 text-[9px] text-slate-300">
                    <span className="h-2 w-2 rounded-full" style={{ background: c }} /> {l}
                  </span>
                ))}
              </div>
            </div>
          </div>
          {selectedRisk && (
            <div className="pointer-events-none absolute bottom-3 left-3 rounded border border-edge bg-panel/90 px-3 py-2 backdrop-blur-sm">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ background: levelFill(selectedRisk.level) }} />
                <span className="text-[11px] font-medium text-slate-200">{selectedRisk.location_name}</span>
                <span className="telemetry text-[11px] font-semibold" style={{ color: levelFill(selectedRisk.level) }}>
                  {(selectedRisk.risk_probability * 100).toFixed(0)}%
                </span>
                <span className="telemetry text-[10px] text-mono">{selectedRisk.trend} · conf {(selectedRisk.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          )}
        </main>

        {/* RIGHT PANEL */}
        <aside className="flex w-[400px] shrink-0 flex-col">
          <Tabs tabs={TABS} active={tab} onChange={setTab} />
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-3">
            <div className="min-h-0 flex-1 overflow-y-auto">
              {tab === "detail" && (selectedId ? <RiskDetailPanel riskId={selectedId} /> : <EmptyPanel label="select a zone from the map or risk rail" />)}
              {tab === "causal" && (selectedId ? <CausalChain riskId={selectedId} /> : <EmptyPanel label="select a zone from the map or risk rail" />)}
              {tab === "memory" && (selectedId ? <MemoryPanel riskId={selectedId} /> : <EmptyPanel label="select a zone from the map or risk rail" />)}
              {tab === "decide" && <DecisionPanel riskName={selectedRisk?.location_name ?? "pilot"} />}
              {tab === "simulate" && (selectedId ? <SimulationSandbox riskId={selectedId} /> : <EmptyPanel label="select a zone from the map or risk rail" />)}
              {tab === "agents" && (selectedId ? <DebatePanel riskId={selectedId} riskName={selectedRisk?.location_name ?? ""} /> : <EmptyPanel label="select a zone from the map or risk rail" />)}
              {tab === "copilot" && (selectedId ? <Copilot riskId={selectedId} /> : <EmptyPanel label="select a zone from the map or risk rail" />)}
              {tab === "validation" && <ValidationPanel />}
            </div>
          {risk && risk.llm_mode && (
            <div className="border-t border-edge px-3 py-1.5 telemetry text-[9px] uppercase tracking-widest text-mono">
              every score is explainable · model {risk.model_name} · {risk.evidence.length} evidence objects
            </div>
          )}
          </div>
        </aside>
      </div>
    </div>
  );
}
