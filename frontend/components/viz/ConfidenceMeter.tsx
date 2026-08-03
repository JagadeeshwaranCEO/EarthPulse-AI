export function ConfidenceMeter({ confidence }: { confidence: number }) {
  const color = confidence >= 0.7 ? "#10B981" : confidence >= 0.55 ? "#3B82F6" : "#F59E0B";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <span className="telemetry text-[10px] uppercase tracking-widest text-mono">confidence</span>
        <span className="telemetry text-[11px] font-semibold" style={{ color }}>{(confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="flex gap-1">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="h-2 flex-1 rounded-sm" style={{ background: i < confidence * 10 ? color : "#161D29" }} />
        ))}
      </div>
      {confidence < 0.55 && <p className="text-[10px] text-accent-amber">Low confidence → AI debate engaged</p>}
    </div>
  );
}
