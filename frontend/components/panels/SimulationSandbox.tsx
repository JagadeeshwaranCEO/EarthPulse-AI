"use client";

import { useEffect, useState } from "react";
import { api, type Intervention, type SimulationResult } from "@/lib/api";
import { Badge, Panel } from "@/components/ui/Panel";

export function SimulationSandbox({ riskId }: { riskId: string }) {
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [sliders, setSliders] = useState<Record<string, number>>({});
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.interventions().then((list) => {
      setInterventions(list);
      setSliders(Object.fromEntries(list.map((i) => [i.id, 0])));
    }).catch(() => {});
  }, []);

  const run = async () => {
    setRunning(true);
    try {
      setResult(await api.simulate(riskId, sliders));
    } finally {
      setRunning(false);
    }
  };

  const active = Object.entries(sliders).filter(([, v]) => v > 0).length;
  const before = result?.baseline.probability;
  const after = result?.after.probability;

  return (
    <Panel
      title="what-if sandbox"
      right={<Badge tone={active ? "amber" : "slate"}>{active ? `${active} interventions` : "baseline"}</Badge>}
    >
      <div className="space-y-3 p-3">
        <div className="space-y-2.5">
          {interventions.map((i) => (
            <div key={i.id} className="rounded border border-edge bg-panel2 p-2">
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] font-medium text-slate-200">{i.name}</span>
                <Badge tone={i.kind === "policy" ? "blue" : i.kind === "operational" ? "amber" : "slate"}>{i.kind}</Badge>
              </div>
              <p className="mt-0.5 text-[10px] leading-snug text-mono">{i.description}</p>
              <input
                type="range" min={0} max={1} step={0.05}
                value={sliders[i.id] ?? 0}
                onChange={(e) => setSliders((s) => ({ ...s, [i.id]: Number(e.target.value) }))}
                className="mt-1.5 w-full accent-amber-500"
              />
            </div>
          ))}
        </div>

        <button
          onClick={run} disabled={running || active === 0}
          className="w-full rounded border border-accent-amber/60 bg-accent-amber/10 py-2 text-[12px] font-semibold text-accent-amber transition-colors hover:bg-accent-amber/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {running ? "simulating…" : active === 0 ? "move sliders to run what-if" : "run simulation"}
        </button>

        {result && (
          <div className="space-y-2.5">
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded border border-edge bg-panel2 p-2.5">
                <div className="telemetry text-[9px] uppercase tracking-widest text-mono">baseline</div>
                <div className="telemetry text-2xl font-semibold text-slate-200">{(before! * 100).toFixed(0)}%</div>
                <div className="telemetry text-[10px] text-mono">sev {result.baseline.severity.toFixed(1)} · ${(result.baseline.expected_damage_usd / 1000).toFixed(0)}k est.</div>
              </div>
              <div className="rounded border border-accent-green/40 bg-accent-green/5 p-2.5">
                <div className="telemetry text-[9px] uppercase tracking-widest text-accent-green">after intervention</div>
                <div className="telemetry text-2xl font-semibold text-accent-green">{(after! * 100).toFixed(0)}%</div>
                <div className="telemetry text-[10px] text-mono">sev {result.after.severity.toFixed(1)} · ${(result.after.expected_damage_usd / 1000).toFixed(0)}k est.</div>
              </div>
            </div>

            <div className="rounded border border-edge bg-panel2 p-2.5">
              <div className="flex items-baseline justify-between">
                <span className="telemetry text-[9px] uppercase tracking-widest text-mono">damage reduction</span>
                <span className="telemetry text-lg font-semibold text-accent-green">{result.deltas.damage_reduction_pct.toFixed(1)}%</span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-panel">
                <div className="h-full rounded bg-accent-green transition-all duration-700" style={{ width: `${result.deltas.damage_reduction_pct}%` }} />
              </div>
              <div className="telemetry mt-1.5 text-[10px] text-mono">
                ${result.deltas.damage_avoided_usd.toFixed(0)} avoided · p ↓ {(result.deltas.probability_reduction * 100).toFixed(1)}pp
              </div>
            </div>

            <div className="rounded border border-accent-blue/40 bg-accent-blue/5 p-2.5">
              <div className="telemetry text-[9px] uppercase tracking-widest text-accent-blue">carbon impact ledger</div>
              <div className="mt-1 grid grid-cols-3 gap-1 text-center">
                <div>
                  <div className="telemetry text-[13px] font-semibold text-slate-200">{fmtKg(result.carbon_ledger.carbon_spent_kg)}</div>
                  <div className="telemetry text-[9px] text-mono">spent</div>
                </div>
                <div>
                  <div className="telemetry text-[13px] font-semibold text-accent-green">{fmtKg(result.carbon_ledger.co2e_avoided_kg)}</div>
                  <div className="telemetry text-[9px] text-mono">CO2e avoided</div>
                </div>
                <div>
                  <div className="telemetry text-[13px] font-semibold text-accent-blue">{fmtKg(result.carbon_ledger.net_kg)}</div>
                  <div className="telemetry text-[9px] text-mono">net</div>
                </div>
              </div>
              <div className="telemetry mt-1 text-[9px] text-mono/70">{result.carbon_ledger.method}</div>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

function fmtKg(kg: number) {
  return kg >= 1000 ? `${(kg / 1000).toFixed(1)}t` : `${kg.toFixed(0)}kg`;
}
