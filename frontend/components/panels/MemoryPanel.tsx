"use client";

import { useEffect, useState } from "react";
import { api, type CompareAnalysis, type Evolution, type MemoryView, type ScientistExplanation } from "@/lib/api";
import { Badge, Panel } from "@/components/ui/Panel";
import { EvolutionChart } from "@/components/viz/EvolutionChart";

export function MemoryPanel({ riskId }: { riskId: string }) {
  const [mem, setMem] = useState<MemoryView | null>(null);
  const [ev, setEv] = useState<Evolution | null>(null);
  const [scientist, setScientist] = useState<ScientistExplanation | null>(null);
  const [cmp, setCmp] = useState<CompareAnalysis | null>(null);
  const [mode, setMode] = useState<"operator" | "compare" | "scientist">("operator");

  useEffect(() => {
    let alive = true;
    setMode("operator");
    setScientist(null);
    setCmp(null);
    api.memory(riskId).then((m) => alive && setMem(m)).catch(() => {});
    api.evolution(riskId).then((e) => alive && setEv(e)).catch(() => {});
    api.scientist(riskId).then((s) => alive && setScientist(s)).catch(() => {});
    api.compare(riskId).then((c) => alive && setCmp(c)).catch(() => {});
    return () => { alive = false; };
  }, [riskId]);

  return (
    <Panel
      title="environmental memory & evolution"
      right={
        <div className="flex items-center gap-1 rounded border border-edge p-0.5">
          <button onClick={() => setMode("operator")} className={`telemetry rounded px-1.5 py-0.5 text-[9px] uppercase tracking-widest ${mode === "operator" ? "bg-accent-blue/20 text-accent-blue" : "text-mono"}`}>operator</button>
          <button onClick={() => setMode("compare")} className={`telemetry rounded px-1.5 py-0.5 text-[9px] uppercase tracking-widest ${mode === "compare" ? "bg-accent-red/20 text-accent-red" : "text-mono"}`}>live analysis</button>
          <button onClick={() => setMode("scientist")} className={`telemetry rounded px-1.5 py-0.5 text-[9px] uppercase tracking-widest ${mode === "scientist" ? "bg-accent-amber/20 text-accent-amber" : "text-mono"}`}>explain like a scientist</button>
        </div>
      }
    >
      {mode === "scientist" ? <ScientistPane s={scientist} /> : mode === "compare" ? <ComparePane cmp={cmp} /> : <OperatorPane mem={mem} ev={ev} />}
    </Panel>
  );
}

const TONE_UI = {
  red: { border: "border-accent-red/50", text: "text-accent-red", bg: "bg-accent-red/10" },
  amber: { border: "border-accent-amber/50", text: "text-accent-amber", bg: "bg-accent-amber/10" },
  blue: { border: "border-accent-blue/50", text: "text-accent-blue", bg: "bg-accent-blue/10" },
} as const;

function ComparePane({ cmp }: { cmp: CompareAnalysis | null }) {
  const [showReport, setShowReport] = useState(false);
  if (!cmp) return <p className="p-4 text-xs text-mono">running live comparative analysis…</p>;
  const tone = TONE_UI[cmp.verdict.tone];
  return (
    <div className="space-y-3 p-3">
      <div className={`rounded border ${tone.border} ${tone.bg} p-2.5`}>
        <div className="flex items-center justify-between">
          <span className={`telemetry text-[9px] uppercase tracking-widest ${tone.text}`}>verdict · {cmp.verdict.tone}</span>
          <Badge tone={cmp.verdict.tone === "red" ? "red" : cmp.verdict.tone === "amber" ? "amber" : "blue"}>Δ24h {cmp.verdict.delta_24h >= 0 ? "+" : ""}{(cmp.verdict.delta_24h * 100).toFixed(0)}pp</Badge>
        </div>
        <p className="mt-1.5 text-[12px] font-medium leading-snug text-slate-100">{cmp.verdict.title}</p>
        <p className="mt-1 text-[10px] leading-snug text-slate-300">{cmp.verdict.advice}</p>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="rounded bg-panel p-2">
          <div className="telemetry text-[9px] uppercase tracking-widest text-mono">live now</div>
          <div className="mt-1 text-sm font-semibold text-slate-100">{(cmp.live.risk_probability * 100).toFixed(0)}%</div>
          <div className="text-[9px] uppercase text-mono">{cmp.live.level} · h{cmp.live.hour}</div>
        </div>
        <div className="rounded bg-panel p-2">
          <div className="telemetry text-[9px] uppercase tracking-widest text-mono">24h trajectory</div>
          <div className={`mt-1 text-sm font-semibold ${cmp.evolution.trend === "rising" ? "text-accent-red" : cmp.evolution.trend === "easing" ? "text-accent-green" : "text-slate-100"}`}>{cmp.evolution.trend}</div>
          <div className="text-[9px] uppercase text-mono">peak {(cmp.evolution.peak_probability * 100).toFixed(0)}% @ h{cmp.evolution.peak_at_hour}</div>
        </div>
        <div className="rounded bg-panel p-2">
          <div className="telemetry text-[9px] uppercase tracking-widest text-mono">history / 10y</div>
          <div className="mt-1 text-sm font-semibold text-slate-100">{cmp.history.events_10y} events</div>
          <div className="text-[9px] uppercase text-mono">{cmp.analogues.length} analogue(s) pulled</div>
        </div>
      </div>

      {cmp.previous_records.length > 0 && (
        <div className="rounded border border-edge bg-panel2 p-2">
          <div className="telemetry text-[9px] uppercase tracking-widest text-mono">previous saved predictions · same theatre</div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {cmp.previous_records.map((r, i) => (
              <span key={i} className="rounded bg-panel px-2 py-1 telemetry text-[9px] text-slate-300">
                {new Date(r.generated_at).toLocaleString(undefined, { hour: "2-digit", minute: "2-digit" })} · {(r.risk_probability * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>
      )}

      {cmp.analogues.length > 0 && (
        <div className="rounded border border-edge bg-panel2 p-2">
          <div className="telemetry text-[9px] uppercase tracking-widest text-mono">analogue matches · with live telemetry</div>
          <div className="mt-1.5 space-y-1.5">
            {cmp.analogues.map((a) => (
              <div key={a.event + a.date} className="flex items-center justify-between gap-2 rounded bg-panel px-2 py-1.5">
                <div className="min-w-0">
                  <div className="truncate text-[11px] text-slate-200">{a.event} · {a.date}</div>
                  <div className="truncate text-[9px] text-mono">{a.matching_drivers} drivers matched · {a.divergence}</div>
                </div>
                <div className="text-right">
                  <div className="telemetry text-[11px] font-semibold text-accent-amber">{(a.similarity * 100).toFixed(0)}%</div>
                  <div className="text-[9px] uppercase text-mono">{a.reliability}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => setShowReport(!showReport)}
        className="telemetry w-full rounded border border-edge bg-panel px-2 py-1.5 text-[10px] uppercase tracking-widest text-accent-blue hover:border-accent-blue/60"
      >
        {showReport ? "hide" : "show"} briefing report · markdown
      </button>
      {showReport && (
        <pre className="whitespace-pre-wrap break-words rounded border border-edge bg-panel p-2.5 font-mono text-[9px] leading-relaxed text-slate-300">{cmp.markdown}</pre>
      )}
    </div>
  );
}

function OperatorPane({ mem, ev }: { mem: MemoryView | null; ev: Evolution | null }) {
  return (
    <div className="space-y-3 p-3">
      {mem && (
        <div className="rounded border border-edge bg-panel2 p-2.5">
          <div className="flex items-center justify-between">
            <span className="telemetry text-[10px] uppercase tracking-widest text-mono">historical record · {mem.location_name}</span>
            <Badge tone="blue">{mem.historical_floods_10y} floods / 10y</Badge>
          </div>
          <p className="mt-1.5 text-[11px] leading-snug text-slate-200">{mem.headline}</p>

          {mem.analogue_breakdown && (
            <div className="mt-2.5 space-y-2.5">
              <div className="rounded border border-accent-amber/40 bg-accent-amber/5 p-2">
                <div className="flex items-center justify-between">
                  <span className="telemetry text-[9px] uppercase tracking-widest text-accent-amber">analogue divergence</span>
                  <Badge tone={mem.analogue_breakdown.estimated_reliability === "High" ? "green" : mem.analogue_breakdown.estimated_reliability === "Moderate" ? "amber" : "red"}>
                    reliability {mem.analogue_breakdown.estimated_reliability}
                  </Badge>
                </div>
                <div className="mt-1.5 grid grid-cols-1 gap-1">
                  {mem.analogue_breakdown.matching_drivers.map((d) => (
                    <div key={d.feature} className="flex items-center justify-between gap-2 text-[10px]">
                      <span className="text-slate-300">{d.driver}</span>
                      <span className={`telemetry ${d.matched ? "text-accent-green" : "text-mono"} ${d.matched ? "" : "line-through"}`}>
                        {d.matched ? "✓ matched" : "· differs"}
                      </span>
                    </div>
                  ))}
                </div>
                {mem.analogue_breakdown.critical_divergences.length > 0 && (
                  <div className="mt-2 rounded bg-panel p-2">
                    <div className="telemetry text-[9px] uppercase tracking-widest text-accent-blue">critical divergences · where today differs</div>
                    <ul className="mt-1 space-y-0.5 text-[10px] leading-snug text-slate-300">
                      {mem.analogue_breakdown.critical_divergences.map((v, i) => <li key={i}>· {v}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="mt-2.5 space-y-2">
            {mem.top_analogues.map((a) => (
              <div key={a.event + a.date} className="rounded border border-edge bg-panel p-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-medium text-slate-200">{a.event} · {a.date}</span>
                  <span className="telemetry text-[10px] font-semibold text-accent-amber">{(a.similarity * 100).toFixed(0)}% match</span>
                </div>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-panel2">
                  <div className="h-full rounded bg-accent-amber" style={{ width: `${a.similarity * 100}%` }} />
                </div>
                <p className="mt-1 text-[10px] text-mono">sev {a.severity}/5 · {a.description}</p>
              </div>
            ))}
          </div>
          <div className="mt-2.5 grid grid-cols-2 gap-2">
            <div className="rounded bg-panel p-2">
              <div className="telemetry text-[9px] uppercase tracking-widest text-accent-red">known vulnerabilities</div>
              <ul className="mt-1 space-y-0.5 text-[10px] text-slate-300">
                {mem.known_vulnerabilities.map((v, i) => <li key={i}>· {v}</li>)}
              </ul>
            </div>
            <div className="rounded bg-panel p-2">
              <div className="telemetry text-[9px] uppercase tracking-widest text-accent-blue">choke points</div>
              <ul className="mt-1 space-y-0.5 text-[10px] text-slate-300">
                {mem.choke_points.map((v, i) => <li key={i}>· {v}</li>)}
              </ul>
            </div>
          </div>
        </div>
      )}

      {ev && (
        <div className="rounded border border-edge bg-panel2 p-2">
          <div className="mb-1 flex items-center justify-between px-1">
            <span className="telemetry text-[10px] uppercase tracking-widest text-mono">risk evolution · hour-by-hour</span>
            <span className="telemetry text-[10px] text-mono">
              peak {(ev.peak_probability * 100).toFixed(0)}% @ h{ev.peak_at_hour}
              <span className="ml-2 text-accent-blue">Δ24h {ev.delta_24h >= 0 ? "+" : ""}{(ev.delta_24h * 100).toFixed(0)}pp</span>
            </span>
          </div>
          <EvolutionChart points={ev.points} nowHour={ev.now_hour} />
        </div>
      )}

      {!mem && !ev && <p className="p-4 text-xs text-mono">loading memory store…</p>}
    </div>
  );
}

function ScientistPane({ s }: { s: ScientistExplanation | null }) {
  if (!s) return <p className="p-4 text-xs text-mono">computing full decomposition…</p>;
  return (
    <div className="space-y-3 p-3">
      <div className="flex items-center justify-between rounded border border-edge bg-panel2 px-2.5 py-2">
        <span className="telemetry text-[10px] uppercase tracking-widest text-mono">score: {s.model_name}</span>
        <span className="telemetry text-lg font-semibold text-accent-amber">{(s.score * 100).toFixed(0)}%</span>
      </div>
      <div className="space-y-2">
        <div className="telemetry text-[9px] uppercase tracking-widest text-mono">computation · step by step</div>
        {s.formula_steps.map((step, i) => (
          <div key={i} className="rounded border border-edge bg-panel2 p-2">
            <code className="block whitespace-pre-wrap break-words font-mono text-[10px] leading-snug text-accent-blue">{step.equation}</code>
            <p className="mt-1 text-[10px] leading-snug text-mono">{step.explanation}</p>
          </div>
        ))}
      </div>
      <div>
        <div className="mb-1 telemetry text-[9px] uppercase tracking-widest text-mono">dominant factors · weighted</div>
        <div className="space-y-1.5">
          {s.dominant_factors.map((f) => (
            <div key={f.feature} className="flex items-center gap-2">
              <span className="w-36 shrink-0 truncate text-[11px] text-slate-300">{f.feature.replace(/_/g, " ")}</span>
              <div className="h-2 flex-1 overflow-hidden rounded bg-panel2">
                <div className="h-full rounded bg-accent-amber" style={{ width: `${Math.min(100, f.influence * 100)}%` }} />
              </div>
              <span className="telemetry w-8 text-right text-[10px] text-mono">×{f.weight.toFixed(1)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded border border-edge bg-panel2 p-2">
        <div className="telemetry text-[9px] uppercase tracking-widest text-mono">uncertainty bounds</div>
        <div className="mt-1 flex items-center gap-2">
          <span className="telemetry text-[10px] text-mono">lower {(s.uncertainty.lower * 100).toFixed(1)}%</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded bg-panel">
            <div className="relative h-full rounded bg-accent-blue" style={{ width: `${(s.uncertainty.upper - s.uncertainty.lower) * 100}%`, marginLeft: `${s.uncertainty.lower * 100}%` }} />
          </div>
          <span className="telemetry text-[10px] text-mono">upper {(s.uncertainty.upper * 100).toFixed(1)}%</span>
        </div>
      </div>
      <div className="rounded border border-accent-amber/40 bg-accent-amber/5 p-2.5">
        <span className="telemetry text-[9px] uppercase tracking-widest text-accent-amber">limitations</span>
        <ul className="mt-1 space-y-0.5 text-[10px] text-slate-300">
          {s.limitations.map((l, i) => <li key={i}>· {l}</li>)}
        </ul>
        <p className="mt-1.5 text-[9px] text-mono/70">{s.provenance_note}</p>
      </div>
    </div>
  );
}
