"use client";

import { useEffect, useState } from "react";
import { api, type TrustScore } from "@/lib/api";

const TONES: Record<string, string> = {
  High: "border-accent-green/60 bg-accent-green/10 text-accent-green",
  Moderate: "border-accent-amber/60 bg-accent-amber/10 text-accent-amber",
  Low: "border-accent-red/60 bg-accent-red/10 text-accent-red",
};

export function TrustPill({ riskId }: { riskId: string }) {
  const [trust, setTrust] = useState<TrustScore | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    api.trust(riskId).then((t) => alive && setTrust(t)).catch(() => {});
    return () => { alive = false; };
  }, [riskId]);

  if (!trust) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`telemetry flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider backdrop-blur-sm transition-colors ${TONES[trust.level]}`}
        title="operational data trust — click for decomposition"
      >
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
        data trust · {trust.level.toLowerCase()}
      </button>

      {open && (
        <div className="absolute right-0 top-7 z-20 w-64 rounded-lg border border-edge bg-panel/95 p-2.5 shadow-panel backdrop-blur-md">
          <div className="flex items-baseline justify-between">
            <span className="telemetry text-[10px] uppercase tracking-widest text-mono">operational data trust</span>
            <span className={`telemetry text-[13px] font-semibold ${TONES[trust.level].split(" ")[2]}`}>{trust.score.toFixed(0)}</span>
          </div>
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded bg-panel2">
            <div className="h-full rounded transition-all duration-700" style={{ width: `${trust.score}%`, background: trust.level === "High" ? "#10B981" : trust.level === "Moderate" ? "#F59E0B" : "#EF4444" }} />
          </div>
          <p className="mt-1.5 text-[10px] leading-snug text-mono">{trust.reason}</p>
          <ul className="mt-2 space-y-1">
            {trust.checks.map((c) => (
              <li key={c.label} className="flex items-start gap-1.5 text-[10px] leading-snug">
                <span className={c.ok ? "text-accent-green" : "text-accent-red"}>{c.ok ? "✓" : "✗"}</span>
                <span className={c.ok ? "text-slate-300" : "text-slate-400"}>
                  {c.label}
                  <span className="text-mono/70"> — {c.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
