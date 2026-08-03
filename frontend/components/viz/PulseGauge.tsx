const BANDS = ["stable", "watchful", "stressed", "critical"] as const;

export function PulseGauge({ score, band }: { score: number; band: string }) {
  const pct = Math.min(100, Math.max(0, (score / 1000) * 100));
  const color = score >= 750 ? "#10B981" : score >= 550 ? "#3B82F6" : score >= 300 ? "#F59E0B" : "#EF4444";
  const bandColor: Record<string, string> = { stable: "#10B981", watchful: "#3B82F6", stressed: "#F59E0B", critical: "#EF4444" };
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-28 w-28">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r="42" fill="none" stroke="#161D29" strokeWidth="9" />
          <circle
            cx="50" cy="50" r="42" fill="none" stroke={color} strokeWidth="9" strokeLinecap="round"
            strokeDasharray={`${(pct / 100) * 264} 264`} className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="telemetry text-3xl font-semibold text-slate-100">{Math.round(score)}</span>
          <span className="telemetry text-[9px] uppercase tracking-widest text-mono">/ 1000</span>
        </div>
      </div>
      <div className="flex w-full items-center justify-between px-1">
        {BANDS.map((b) => (
          <span key={b} className={`telemetry text-[8px] uppercase tracking-widest ${band === b ? "font-semibold" : "text-mono/60"}`} style={band === b ? { color: bandColor[b] } : undefined}>
            {b}
          </span>
        ))}
      </div>
      <span className="telemetry text-[10px] uppercase tracking-widest" style={{ color: bandColor[band as string] ?? "#7C8FA6" }}>
        Planet Pulse · {band}
      </span>
    </div>
  );
}
