"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { levelFill, type RiskSummary } from "@/lib/api";

function SearchGlyph() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

export function SearchBar({ risks, onSelect }: { risks: RiskSummary[]; onSelect: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const scored = risks
      .map((r) => {
        const name = r.location_name.toLowerCase();
        const region = (r.region ?? "").toLowerCase();
        let score = 0;
        if (name.startsWith(q)) score = 3;
        else if (name.includes(q)) score = 2;
        else if (region.includes(q)) score = 1;
        return { r, score };
      })
      .filter((s) => s.score > 0);
    scored.sort((a, b) => b.score - a.score || b.r.risk_probability - a.r.risk_probability);
    return scored.slice(0, 8).map((s) => s.r);
  }, [query, risks]);

  const hazardLabel = (t: string) => t.toLowerCase();

  useEffect(() => {
    const close = () => setOpen(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  const pick = (r: RiskSummary) => {
    onSelect(r.location_id);
    setQuery("");
    setOpen(false);
  };

  return (
    <div ref={rootRef} className="pointer-events-auto absolute left-1/2 top-3 z-[500] w-[340px] -translate-x-1/2">
      <div className="flex items-center gap-2 rounded border border-edge bg-panel/95 px-2.5 py-1.5 backdrop-blur-sm shadow-[0_4px_18px_rgba(0,0,0,0.45)]">
        <span className="text-mono"><SearchGlyph /></span>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && matches[0]) pick(matches[0]);
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder="search a zone, city or district…"
          className="w-full bg-transparent text-[12px] text-slate-200 outline-none placeholder:text-mono"
        />
        <span className="telemetry shrink-0 text-[9px] uppercase tracking-widest text-mono">{risks.length} zones</span>
      </div>

      {open && query.trim() && (
        <div className="mt-1 overflow-hidden rounded border border-edge bg-panel/95 backdrop-blur-sm shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
          {matches.length === 0 ? (
            <div className="px-3 py-4 text-center text-[11px] text-mono">
              no problem zones match “{query.trim()}”
            </div>
          ) : (
            <ul className="max-h-[320px] overflow-y-auto">
              {matches.map((r) => (
                <li key={r.location_id}>
                  <button
                    onClick={() => pick(r)}
                    className="group flex w-full items-center gap-2 border-b border-edge/50 px-3 py-2 text-left last:border-0 hover:bg-panel2"
                  >
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: levelFill(r.level) }} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12px] font-medium text-slate-200">{r.location_name}</span>
                      <span className="telemetry block truncate text-[9px] uppercase tracking-widest text-mono">
                        {hazardLabel(r.event_type)} · {r.region}
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block text-[12px] font-semibold" style={{ color: levelFill(r.level) }}>
                        {(r.risk_probability * 100).toFixed(0)}%
                      </span>
                      <span className="telemetry block text-[9px] uppercase tracking-widest" style={{ color: levelFill(r.level) }}>
                        {r.level}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-edge px-3 py-1.5 telemetry text-[9px] uppercase tracking-widest text-mono">
            {matches.length} problem spot{matches.length === 1 ? "" : "s"} · click to focus the map
          </div>
        </div>
      )}
    </div>
  );
}