"use client";

import { useEffect, useState } from "react";
import { api, type CausalNode } from "@/lib/api";
import { Panel } from "@/components/ui/Panel";

const KIND_STYLE: Record<string, string> = {
  cause: "border-accent-blue text-accent-blue",
  mechanism: "border-accent-amber text-accent-amber",
  condition: "border-mono text-mono",
  risk: "border-accent-red text-accent-red",
};

export function CausalChain({ riskId }: { riskId: string }) {
  const [chain, setChain] = useState<{ nodes: CausalNode[]; edges: { source: string; target: string; label: string }[] } | null>(null);

  useEffect(() => {
    let alive = true;
    api.risk(riskId).then((d) => alive && setChain(d.causal_chain)).catch(() => {});
    return () => { alive = false; };
  }, [riskId]);

  if (!chain) {
    return <Panel title="causal chain explorer"><p className="p-4 text-xs text-mono">loading…</p></Panel>;
  }

  const byId = new Map(chain.nodes.map((n) => [n.id, n]));

  return (
    <Panel title="causal chain explorer — why is this risk forming?">
      <div className="flex flex-col items-center gap-0 p-4">
        {chain.nodes.map((node, i) => {
          const children = chain.edges.filter((e) => e.source === node.id);
          return (
            <div key={node.id} className="flex w-full flex-col items-center">
              <div className={`w-64 rounded border bg-panel2 p-2.5 text-center ${KIND_STYLE[node.kind] ?? "border-edge text-slate-200"}`}>
                <div className="telemetry text-[9px] uppercase tracking-widest opacity-80">{node.kind}</div>
                <div className="text-[12px] font-medium text-slate-100">{node.label}</div>
                <div className="telemetry mt-0.5 text-[10px] text-mono">{node.value} · conf {(node.confidence * 100).toFixed(0)}%</div>
              </div>
              {i < chain.nodes.length - 1 && (
                <div className="flex flex-col items-center py-0.5">
                  <div className="h-3 w-px border-l border-dashed border-mono/50" />
                  {children[0] && <div className="telemetry px-2 text-center text-[9px] text-mono/70">{children[0].label}</div>}
                  <div className="h-3 w-px border-l border-dashed border-mono/50" />
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="border-t border-edge p-2 text-center telemetry text-[9px] text-mono">
        {chain.nodes.length} nodes · {chain.edges.length} causal links · evidence-traceable
        {byId.size > 0 && ` · root cause: ${byId.get(chain.nodes[0]?.id ?? "")?.label ?? "—"}`}
      </div>
    </Panel>
  );
}
