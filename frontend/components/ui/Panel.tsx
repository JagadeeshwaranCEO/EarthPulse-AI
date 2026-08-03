export function Panel({ title, right, children, className = "" }: { title?: string; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={`flex flex-col rounded-lg border border-edge bg-panel shadow-panel ${className}`}>
      {title && (
        <div className="flex items-center justify-between border-b border-edge px-3 py-2">
          <span className="telemetry text-[11px] font-medium uppercase tracking-widest text-mono">{title}</span>
          {right}
        </div>
      )}
      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}

export function Tabs({ tabs, active, onChange }: { tabs: { id: string; label: string }[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-edge px-2">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`telemetry shrink-0 px-3 py-2 text-[11px] uppercase tracking-widest transition-colors ${
            active === t.id ? "border-b-2 border-accent-blue text-slate-100" : "border-b-2 border-transparent text-mono hover:text-slate-300"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Badge({ children, tone = "slate" }: { children: React.ReactNode; tone?: "red" | "amber" | "blue" | "green" | "slate" }) {
  const tones: Record<string, string> = {
    red: "border-accent-red/60 text-accent-red",
    amber: "border-accent-amber/60 text-accent-amber",
    blue: "border-accent-blue/60 text-accent-blue",
    green: "border-accent-green/60 text-accent-green",
    slate: "border-edge text-mono",
  };
  return <span className={`telemetry rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${tones[tone]}`}>{children}</span>;
}

export function Meter({ value, max = 1, color = "#3B82F6", label }: { value: number; max?: number; color?: string; label?: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <span className="telemetry text-[10px] uppercase tracking-widest text-mono">{label ?? "level"}</span>
        <span className="telemetry text-[11px] font-semibold" style={{ color }}>{value.toFixed(2)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded bg-panel2">
        <div className="h-full rounded transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
