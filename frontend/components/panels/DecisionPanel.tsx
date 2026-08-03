"use client";

import { useState } from "react";
import { api, type MissionBrief, type OptimizeResponse, type ResourceInventory } from "@/lib/api";
import { Badge, Panel } from "@/components/ui/Panel";

const DEFAULT_INVENTORY: ResourceInventory = { boats: 12, pumps: 8, shelters: 5, budget_inr_crores: 15, personnel: 40 };

export function DecisionPanel({ riskName }: { riskName: string }) {
  const [inv, setInv] = useState<ResourceInventory>(DEFAULT_INVENTORY);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [brief, setBrief] = useState<MissionBrief | null>(null);
  const [running, setRunning] = useState(false);
  const [briefing, setBriefing] = useState(false);
  const [applied, setApplied] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runOptimizer = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await api.optimize(inv);
      setResult(res);
      setBrief(null);
      setApplied(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "optimizer failed");
    } finally {
      setRunning(false);
    }
  };

  const generateBrief = async (strategyId?: string) => {
    setBriefing(true);
    setError(null);
    try {
      const b = await api.brief(inv);
      setBrief(b);
    } catch (e) {
      setError(e instanceof Error ? e.message : "brief failed");
    } finally {
      setBriefing(false);
    }
  };

  const exportBrief = () => {
    if (!brief) return;
    const blob = new Blob([brief.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `earthpulse-brief-${brief.strategy_id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const recommended = result?.strategies.find((s) => s.is_recommended);
  const activeStrategy = result?.strategies.find((s) => s.id === applied);

  return (
    <Panel title="operational resource planner" right={<Badge tone={applied ? "green" : "blue"}>decision layer</Badge>}>
      <div className="space-y-3 p-3">
        {error && <div className="rounded border border-accent-red/50 bg-accent-red/10 px-2 py-1.5 text-[11px] text-accent-red">{error}</div>}

        {/* inventory */}
        <div className="rounded border border-edge bg-panel2 p-2.5">
          <div className="telemetry text-[9px] uppercase tracking-widest text-mono">municipal inventory · constrained</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {(["boats", "pumps", "shelters", "budget_inr_crores"] as const).map((key) => (
              <label key={key} className="block">
                <span className="telemetry text-[10px] uppercase tracking-widest text-mono">{key.replace("_", " ")}</span>
                <input
                  type="number"
                  min={0}
                  value={inv[key]}
                  onChange={(e) => setInv((i) => ({ ...i, [key]: Number(e.target.value) }))}
                  className="mt-0.5 w-full rounded border border-edge bg-panel px-2 py-1 telemetry text-[12px] text-slate-200 outline-none focus:border-accent-blue"
                />
              </label>
            ))}
          </div>
          <button
            onClick={runOptimizer}
            disabled={running}
            className="mt-2.5 w-full rounded border border-accent-blue/60 bg-accent-blue/10 py-2 text-[12px] font-semibold text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:opacity-40"
          >
            {running ? "optimizing…" : "run constrained optimizer"}
          </button>
        </div>

        {/* strategies */}
        {result && (
          <div className="space-y-2">
            <div className="telemetry text-[9px] uppercase tracking-widest text-mono">pareto strategies · {result.inventory.boats} boats · {result.inventory.pumps} pumps · {result.inventory.shelters} shelters</div>

            {/* decision confidence */}
            <div className="rounded border border-accent-blue/40 bg-accent-blue/5 p-2.5">
              <div className="flex items-center justify-between">
                <span className="telemetry text-[9px] uppercase tracking-widest text-accent-blue">decision confidence</span>
                <span className="telemetry text-lg font-semibold text-accent-blue">{(result.analysis.decision_confidence * 100).toFixed(0)}%</span>
              </div>
              <p className="mt-1 text-[10px] leading-snug text-mono">
                probability {result.analysis.recommended_id.replace("strat_", "Strategy ")} remains optimal under precipitation variance
              </p>
              <div className="mt-1.5 grid grid-cols-2 gap-2 text-center">
                <div className="rounded bg-panel p-1.5">
                  <div className="telemetry text-[12px] font-semibold text-slate-200">{result.analysis.robustness_rainfall_pct > 0 ? `+${result.analysis.robustness_rainfall_pct}%` : "0%"}</div>
                  <div className="telemetry text-[8px] uppercase tracking-widest text-mono">rainfall robustness</div>
                </div>
                <div className="rounded bg-panel p-1.5">
                  <div className="telemetry text-[12px] font-semibold text-slate-200">{(result.analysis.prediction_confidence * 100).toFixed(0)}%</div>
                  <div className="telemetry text-[8px] uppercase tracking-widest text-mono">prediction conf.</div>
                </div>
              </div>
              {result.analysis.fallback_strategy_id && (
                <div className="mt-1.5 rounded border border-accent-amber/40 bg-accent-amber/5 px-2 py-1.5 text-[10px] leading-snug text-accent-amber">
                  alternate {result.analysis.fallback_strategy_id.replace("strat_", "Strategy ")} advised · {result.analysis.fallback_trigger}
                </div>
              )}
            </div>

            {/* trade-off matrix */}
            <div className="rounded border border-edge bg-panel2 p-2.5">
              <div className="telemetry text-[9px] uppercase tracking-widest text-mono">why the plans differ · trade-off matrix</div>
              <div className="mt-1.5 space-y-1.5">
                {result.strategies.map((s) => {
                  const meta = result.analysis.trade_offs[s.id];
                  return (
                    <div key={s.id} className="rounded bg-panel p-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-medium text-slate-200">{s.title.replace("Strategy ", "")}</span>
                        <span className="telemetry text-[9px] text-mono">{meta.objective}</span>
                      </div>
                      <p className="mt-0.5 text-[10px] leading-snug text-mono">{meta.trade_off}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {result.strategies.map((s) => (
              <div key={s.id} className={`rounded border p-2.5 transition-colors ${applied === s.id ? "border-accent-green/70 bg-accent-green/10" : "border-edge bg-panel2"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[12px] font-medium text-slate-200">{s.title.replace("Strategy ", "")}</span>
                  {s.is_recommended && <Badge tone="green">recommended</Badge>}
                </div>
                <p className="mt-1 text-[10px] leading-snug text-mono">{s.rationale}</p>
                <div className="mt-2 grid grid-cols-3 gap-1.5 text-center">
                  <div className="rounded bg-panel p-1.5">
                    <div className="telemetry text-[13px] font-semibold text-accent-blue">{(s.lives_protected / 1000).toFixed(0)}k</div>
                    <div className="telemetry text-[8px] uppercase tracking-widest text-mono">lives</div>
                  </div>
                  <div className="rounded bg-panel p-1.5">
                    <div className="telemetry text-[13px] font-semibold text-accent-amber">₹{s.economic_loss_inr_cr.toFixed(0)}Cr</div>
                    <div className="telemetry text-[8px] uppercase tracking-widest text-mono">resid. loss</div>
                  </div>
                  <div className="rounded bg-panel p-1.5">
                    <div className="telemetry text-[13px] font-semibold text-accent-green">{s.co2_reduction_pct.toFixed(0)}%</div>
                    <div className="telemetry text-[8px] uppercase tracking-widest text-mono">co2</div>
                  </div>
                </div>
                <div className="mt-2 space-y-1">
                  {s.actions.map((a, i) => (
                    <div key={i} className="telemetry text-[10px] leading-snug text-mono">▸ {a}</div>
                  ))}
                </div>
                <button
                  onClick={() => setApplied(applied === s.id ? null : s.id)}
                  className={`mt-2 w-full rounded border py-1.5 text-[11px] font-semibold transition-colors ${
                    applied === s.id ? "border-accent-green/60 bg-accent-green/10 text-accent-green" : "border-edge bg-panel text-slate-300 hover:border-accent-blue/60"
                  }`}
                >
                  {applied === s.id ? "plan active on map" : "apply plan"}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* execution timeline */}
        {result && recommended?.execution_timeline && recommended.execution_timeline.length > 0 && (
          <div className="rounded border border-edge bg-panel2 p-2.5">
            <div className="flex items-center justify-between">
              <span className="telemetry text-[9px] uppercase tracking-widest text-mono">operator timeline · when to act</span>
              <Badge tone="blue">peak h{result.peak_hour}</Badge>
            </div>
            <div className="mt-2 space-y-0">
              {recommended.execution_timeline.map((step, i) => (
                <div key={step.phase} className="relative flex gap-2.5 pb-3 last:pb-0">
                  {i < recommended.execution_timeline.length - 1 && (
                    <span className="absolute left-[7px] top-4 h-full w-px bg-edge" />
                  )}
                  <span className={`mt-0.5 h-3.5 w-3.5 shrink-0 rounded-full border-2 ${i === recommended.execution_timeline.length - 1 ? "border-accent-red bg-accent-red/30" : "border-accent-blue bg-accent-blue/20"}`} />
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="telemetry text-[11px] font-semibold text-slate-200">{step.time}</span>
                      <span className="telemetry text-[9px] uppercase tracking-widest text-accent-amber">{step.phase}</span>
                    </div>
                    <p className="mt-0.5 text-[10px] leading-snug text-mono">{step.action}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* mission brief */}
        <div className="rounded border border-accent-amber/50 bg-accent-amber/5 p-2.5">
          <div className="flex items-center justify-between">
            <span className="telemetry text-[9px] uppercase tracking-widest text-accent-amber">ai mission brief</span>
            {brief && (
              <button onClick={exportBrief} className="telemetry text-[10px] font-semibold text-accent-blue hover:text-slate-200">export .md</button>
            )}
          </div>
          {brief ? (
            <div className="mt-2 max-h-64 overflow-auto rounded border border-edge bg-panel/60 p-2">
              <pre className="whitespace-pre-wrap font-sans text-[10px] leading-relaxed text-slate-300">{brief.markdown}</pre>
            </div>
          ) : (
            <p className="mt-1 text-[10px] leading-snug text-mono">
              Compose the stakeholder brief from the recommended strategy, environmental memory and evolution arc.
            </p>
          )}
          <button
            onClick={() => generateBrief()}
            disabled={briefing || !result}
            className="mt-2 w-full rounded border border-accent-amber/60 bg-accent-amber/10 py-1.5 text-[11px] font-semibold text-accent-amber transition-colors hover:bg-accent-amber/20 disabled:opacity-40"
          >
            {briefing ? "composing…" : brief ? "recompose brief" : "generate mission brief"}
          </button>
        </div>

        <div className="telemetry text-[9px] leading-snug text-mono/60">
          {activeStrategy ? `plan ${activeStrategy.id} active · ${activeStrategy.title}` : "no plan applied yet"} · focused on {riskName}
        </div>
        {result && <div className="telemetry text-[9px] leading-snug text-mono/50">{result.analysis.method}</div>}
      </div>
    </Panel>
  );
}
