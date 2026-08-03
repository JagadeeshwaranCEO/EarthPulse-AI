"use client";

import { useEffect, useState } from "react";
import { api, type DebateResult } from "@/lib/api";
import { Badge, Panel } from "@/components/ui/Panel";

export function DebatePanel({ riskId, riskName }: { riskId: string; riskName: string }) {
  const [debate, setDebate] = useState<DebateResult | null>(null);
  const [forced, setForced] = useState(false);

  useEffect(() => {
    let alive = true;
    api.debate(riskId, forced)
      .then((d) => alive && setDebate(d))
      .catch(() => {});
    return () => { alive = false; };
  }, [riskId, forced]);

  return (
    <Panel
      title="AI debate engine"
      right={
        <div className="flex items-center gap-2">
          <Badge tone={debate?.llm_mode === "live" ? "green" : "slate"}>{debate?.llm_mode === "live" ? "llm live" : "template"}</Badge>
          {debate && debate.statements.length === 0 && (
            <button onClick={() => setForced(true)} className="telemetry text-[10px] text-accent-amber underline">
              force debate
            </button>
          )}
        </div>
      }
    >
      {!debate ? (
        <p className="p-4 text-xs text-mono">loading…</p>
      ) : debate.statements.length === 0 ? (
        <div className="p-4">
          <p className="text-[12px] text-accent-green">{debate.verdict}</p>
          <p className="mt-2 text-[11px] text-mono">
            Agents agree above the confidence threshold — no debate invoked. Force one to see the
            evidence-contrast view for demo purposes.
          </p>
        </div>
      ) : (
        <div className="space-y-3 p-3">
          {debate.statements.map((s, i) => (
            <div key={i} className="rounded border border-edge bg-panel2 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold text-accent-blue">{s.agent}</span>
                <span className="telemetry text-[10px] text-mono">{(s.confidence * 100).toFixed(0)}% conf</span>
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-300">{s.position}</p>
              {s.evidence.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {s.evidence.map((e, j) => <Badge key={j} tone="slate">{e}</Badge>)}
                </div>
              )}
            </div>
          ))}
          <div className="rounded border border-accent-blue/40 bg-accent-blue/5 p-2.5">
            <div className="telemetry text-[9px] uppercase tracking-widest text-accent-blue">moderator verdict</div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-300">{debate.verdict}</p>
          </div>
        </div>
      )}
    </Panel>
  );
}
