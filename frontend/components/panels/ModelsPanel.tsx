"use client";

import { useEffect, useState } from "react";
import { Badge, Panel } from "@/components/ui/Panel";

interface ModelEntry {
  id: string;
  name: string;
  category: string;
  status: string;
  description: string;
  endpoint?: string;
  endpoints?: string[];
  notes?: string;
}

interface ModelsInventory {
  scope: string;
  zones: number;
  generated_at: string;
  store: Record<string, number>;
  llm_mode: string;
  models: ModelEntry[];
}

const CATEGORY_LABEL: Record<string, string> = {
  prediction: "prediction",
  explanation: "explanation",
  decision: "decision",
  governance: "governance",
};

export function ModelsPanel() {
  const [data, setData] = useState<ModelsInventory | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/v1/models")
      .then((r) => r.json())
      .then((d) => alive && setData(d))
      .catch(() => alive && setError("model registry unreachable"));
    return () => {
      alive = false;
    };
  }, []);

  if (error) {
    return (
      <Panel title="model registry">
        <p className="p-4 text-xs text-accent-red">{error}</p>
      </Panel>
    );
  }

  const groups = new Map<string, ModelEntry[]>();
  for (const m of data?.models ?? []) {
    const key = CATEGORY_LABEL[m.category] ?? m.category;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(m);
  }

  return (
    <Panel
      title="model registry · every engine online"
      right={
        data ? (
          <span className="telemetry flex items-center gap-2 text-[9px] uppercase tracking-widest text-mono">
            <Badge tone="green">{data.models.length} live</Badge>
            <Badge tone="slate">{data.scope} · {data.zones} zones</Badge>
          </span>
        ) : undefined
      }
    >
      <div className="space-y-3 p-3">
        {!data && <p className="text-xs text-mono">reading the registry…</p>}

        {data && (
          <>
            <div className="flex flex-wrap items-center gap-2 rounded border border-edge bg-panel1 px-2.5 py-2">
              <span className="telemetry text-[9px] uppercase tracking-widest text-mono">store</span>
              {Object.entries(data.store).map(([k, v]) => (
                <span key={k} className="telemetry text-[10px] text-slate-300">
                  {k.replace(/_/g, " ")} <span className="text-accent-blue">{v}</span>
                </span>
              ))}
              <span className="telemetry ml-auto text-[9px] text-mono">llm {data.llm_mode}</span>
            </div>

            {[...groups.entries()].map(([category, models]) => (
              <div key={category} className="space-y-1.5">
                <div className="telemetry flex items-center gap-2 text-[10px] uppercase tracking-widest text-mono">
                  <span className="text-accent-blue">{category}</span>
                  <span className="h-px flex-1 bg-edge" />
                  <span>{models.length}</span>
                </div>
                {models.map((m) => (
                  <div key={m.id} className="rounded border border-edge bg-panel1 px-2.5 py-2">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-[11px] font-medium text-slate-200">{m.name}</span>
                      <span className="ml-auto shrink-0">
                        <Badge tone={m.status === "live" ? "green" : "slate"}>{m.status}</Badge>
                      </span>
                    </div>
                    <p className="mt-1 text-[10px] leading-relaxed text-mono">{m.description}</p>
                    {(m.endpoint ?? m.endpoints?.[0]) && (
                      <p className="telemetry mt-1 truncate text-[9px] text-mono/80">{(m.endpoint ?? m.endpoints![0])}</p>
                    )}
                  </div>
                ))}
              </div>
            ))}

            <p className="telemetry pt-1 text-[9px] uppercase tracking-widest text-mono">report generated {data.generated_at.slice(0, 19).replace("T", " ")}Z</p>
          </>
        )}
      </div>
    </Panel>
  );
}
