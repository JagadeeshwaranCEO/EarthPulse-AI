"use client";

import { useEffect, useState } from "react";
import { Badge, Panel } from "@/components/ui/Panel";

interface Preset {
  id: string;
  name: string;
  hazard_type: string;
  start_lat: number;
  start_lon: number;
  end_lat: number;
  end_lon: number;
  intensity: number;
  radius_km: number;
  duration_h: number;
}

interface ScenarioRun {
  id: string;
  name: string;
  hazard_type: string;
  start: [number, number];
  end: [number, number];
  intensity: number;
  radius_km: number;
  duration_h: number;
  status: string;
  summary: {
    hazard: string;
    frames: number;
    affected_zones: number;
    critical_peak_zones: number;
    affected_population: number;
    impact_score: number;
    shelter_capacity_recommended: number;
    evacuation_lead_minutes: number;
    first_crisis_h: number | null;
    peak_crisis_h: number;
    top_zones: { id: string; name: string; peak_p: number; peak_t: number; peak_level: string; population: number; shelter_recommended: number }[];
  };
  created_at: string;
}

interface Frame {
  t: number;
  crisis: number;
  zones: { id: string; name: string; p: number; level: string }[];
}

const levelFill = (level: string) =>
  level === "critical" ? "#EF4444" : level === "high" ? "#F59E0B" : level === "moderate" ? "#3B82F6" : "#10B981";

export function ScenarioSim() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selected, setSelected] = useState<Preset | null>(null);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<ScenarioRun | null>(null);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [frameIdx, setFrameIdx] = useState(0);
  const [broadcast, setBroadcast] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/scenarios/presets").then((r) => r.json()).then(setPresets).catch(() => {});
  }, []);

  const launch = async (preset: Preset) => {
    setSelected(preset);
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/scenarios", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...preset, step_h: 1, zoom_h: 1, broadcast }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const created = await res.json();
      const full = await fetch(`/api/v1/scenarios/${created.id}`).then((r) => r.json());
      setRun(full);
      setFrames(full.frames);
      setFrameIdx(0);
    } catch {
      setError("scenario launch failed");
    } finally {
      setRunning(false);
    }
  };

  const frame = frames[frameIdx];

  return (
    <Panel
      title="scenario simulator · digital twin"
      right={run ? <Badge tone={run.summary.critical_peak_zones > 0 ? "red" : "blue"}>{run.summary.hazard} sweep</Badge> : undefined}
    >
      <div className="space-y-3 p-3">
        <div className="flex items-center justify-between">
          <span className="telemetry text-[10px] uppercase tracking-widest text-mono">preset drills</span>
          <label className="telemetry flex items-center gap-1.5 text-[9px] uppercase tracking-widest text-mono">
            <input
              type="checkbox"
              checked={broadcast}
              onChange={(e) => setBroadcast(e.target.checked)}
              className="accent-accent-red"
            />
            raise drill alerts
          </label>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {presets.map((p) => (
            <button
              key={p.id}
              disabled={running}
              onClick={() => launch(p)}
              className={`rounded border px-2.5 py-2 text-left transition-colors disabled:opacity-40 ${
                selected?.id === p.id ? "border-accent-blue/60 bg-accent-blue/10" : "border-edge bg-panel1 hover:bg-panel2"
              }`}
            >
              <div className="text-[11px] font-medium text-slate-200">{p.name}</div>
              <div className="telemetry mt-0.5 text-[9px] text-mono">
                {p.hazard_type} · int {p.intensity} · R{p.radius_km}km · {p.duration_h}h
              </div>
            </button>
          ))}
        </div>
        {selected && <p className="text-[9px] text-mono">selected: {selected.name}</p>}
        {running && <p className="text-xs text-accent-blue">marching the hazard through the theatre…</p>}
        {error && <p className="text-xs text-accent-red">{error}</p>}

        {run && (
          <>
            <div className="rounded border border-edge bg-panel1 p-2.5">
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] font-medium text-slate-200">{run.name}</span>
                <span className="telemetry text-[10px] text-mono">{run.id}</span>
              </div>
              <div className="mt-2 grid grid-cols-4 gap-1.5 text-center">
                <div>
                  <div className="telemetry text-lg font-semibold text-slate-100">{run.summary.affected_zones}</div>
                  <div className="telemetry text-[8px] uppercase tracking-widest text-mono">zones hit</div>
                </div>
                <div>
                  <div className="telemetry text-lg font-semibold text-accent-red">{run.summary.critical_peak_zones}</div>
                  <div className="telemetry text-[8px] uppercase tracking-widest text-mono">critical peak</div>
                </div>
                <div>
                  <div className="telemetry text-lg font-semibold text-accent-amber">{run.summary.affected_population.toLocaleString()}</div>
                  <div className="telemetry text-[8px] uppercase tracking-widest text-mono">pop exposed</div>
                </div>
                <div>
                  <div className="telemetry text-lg font-semibold text-accent-blue">{run.summary.impact_score}</div>
                  <div className="telemetry text-[8px] uppercase tracking-widest text-mono">impact score</div>
                </div>
              </div>
              <div className="telemetry mt-2 grid grid-cols-2 gap-1 text-[9px] text-mono">
                <span>evacuation lead <span className="text-slate-300">{run.summary.evacuation_lead_minutes} min</span></span>
                <span>shelter needed <span className="text-slate-300">{run.summary.shelter_capacity_recommended.toLocaleString()}</span></span>
                <span>first crisis <span className="text-slate-300">h{run.summary.first_crisis_h ?? "—"}</span></span>
                <span>peak crisis <span className="text-slate-300">h{run.summary.peak_crisis_h}</span></span>
              </div>
            </div>

            {frame && (
              <div className="rounded border border-edge bg-panel1 p-2.5">
                <div className="flex items-center gap-2">
                  <span className="telemetry shrink-0 text-[10px] uppercase tracking-widest text-mono">h{frame.t}</span>
                  <input
                    type="range" min={0} max={Math.max(0, frames.length - 1)} step={1}
                    value={frameIdx}
                    onChange={(e) => setFrameIdx(Number(e.target.value))}
                    className="w-full accent-accent-blue"
                  />
                  <Badge tone={frame.crisis > 0 ? "red" : "slate"}>{frame.crisis} crisis</Badge>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-1">
                  {frame.zones.filter((z) => z.p >= 0.3).sort((a, b) => b.p - a.p).slice(0, 10).map((z) => (
                    <div key={z.id} className="flex items-center gap-1.5">
                      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: levelFill(z.level) }} />
                      <span className="truncate text-[10px] text-slate-300">{z.name}</span>
                      <span className="telemetry ml-auto text-[10px] font-semibold" style={{ color: levelFill(z.level) }}>
                        {(z.p * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <div className="telemetry flex items-center gap-2 text-[10px] uppercase tracking-widest text-mono">
                <span className="text-accent-blue">peak exposure · top zones</span>
                <span className="h-px flex-1 bg-edge" />
              </div>
              {run.summary.top_zones.map((z) => (
                <div key={z.id} className="flex items-center gap-2 rounded border border-edge bg-panel1 px-2.5 py-1.5">
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: levelFill(z.peak_level) }} />
                  <span className="truncate text-[10px] text-slate-300">{z.name}</span>
                  <span className="telemetry ml-auto text-[9px] text-mono">peak h{z.peak_t}</span>
                  <span className="telemetry w-12 text-right text-[10px] font-semibold" style={{ color: levelFill(z.peak_level) }}>
                    {(z.peak_p * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}
