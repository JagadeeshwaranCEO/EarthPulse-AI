"use client";

export function CrisisBanner({ crisis, alertCount }: { crisis: boolean; alertCount: number }) {
  if (!crisis) return null;
  const ticker = "EARTHPULSE CRISIS MODE ENGAGED · CRITICAL FLOOD RISK DETECTED · PRIORITIZE CIVIC RESPONSE · ";
  return (
    <div className="relative z-[1000] overflow-hidden border-b border-accent-red bg-accent-red/15">
      <div className="flex items-center gap-3 px-4 py-1.5">
        <span className="blink h-2.5 w-2.5 shrink-0 rounded-full bg-accent-red" />
        <span className="telemetry text-[11px] font-semibold tracking-widest text-accent-red">CRISIS COMMAND CENTER</span>
        <span className="telemetry text-[10px] text-slate-300">{alertCount} active alerts</span>
        <div className="relative ml-auto w-[340px] overflow-hidden">
          <div className="ticker-scroll whitespace-nowrap telemetry text-[10px] text-accent-red">
            {ticker.repeat(3)}
          </div>
        </div>
      </div>
    </div>
  );
}
