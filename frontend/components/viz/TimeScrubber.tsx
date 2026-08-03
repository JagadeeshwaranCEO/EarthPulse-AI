"use client";

import { useState } from "react";

export function TimeScrubber({ hour, max, onScrub, running }: { hour: number; max: number; onScrub: (h: number) => void; running: boolean }) {
  const [dragging, setDragging] = useState(false);
  const [local, setLocal] = useState(hour);
  const value = dragging ? local : hour;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="telemetry text-[10px] uppercase tracking-widest text-mono">sim time — digital twin</span>
        <span className="telemetry text-[11px] text-slate-200">
          T+{Math.floor(value)}h / {max}h {running && <span className="text-accent-green blink">● LIVE</span>}
        </span>
      </div>
      <input
        type="range" min={30} max={max} step={1} value={value}
        onChange={(e) => { setDragging(true); setLocal(Number(e.target.value)); }}
        onMouseUp={() => { setDragging(false); onScrub(local); }}
        onTouchEnd={() => { setDragging(false); onScrub(local); }}
        className="w-full accent-blue-500"
      />
      <div className="flex justify-between telemetry text-[9px] text-mono">
        <span>onset</span><span>warning</span><span>peak</span><span>easing</span>
      </div>
    </div>
  );
}
