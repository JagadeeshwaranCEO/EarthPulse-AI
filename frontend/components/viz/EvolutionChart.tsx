"use client";

import { Line, LineChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EvolutionPoint } from "@/lib/api";

export function EvolutionChart({ points, nowHour }: { points: EvolutionPoint[]; nowHour: number }) {
  const data = points.map((p) => ({
    hour: `h${p.hour}`,
    p: p.risk_probability,
    level: p.level,
    isNow: p.is_now,
  }));
  return (
    <ResponsiveContainer width="100%" height={170}>
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -22 }}>
        <CartesianGrid stroke="#1B2433" strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="hour" tick={{ fill: "#7C8FA6", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: "#243043" }} tickLine={false} interval={Math.ceil(data.length / 14)} />
        <YAxis domain={[0, 1]} tick={{ fill: "#7C8FA6", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: "#10151E", border: "1px solid #243043", borderRadius: 6, fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}
          formatter={(v: number | string | (number | string)[]) => (Array.isArray(v) ? v : `${(Number(v) * 100).toFixed(0)}%`)}
        />
        <ReferenceLine x={`h${nowHour}`} stroke="#F59E0B" strokeDasharray="4 4" label={{ value: "now", fill: "#F59E0B", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} />
        <Line type="monotone" dataKey="p" stroke="#F59E0B" strokeWidth={1.6} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
