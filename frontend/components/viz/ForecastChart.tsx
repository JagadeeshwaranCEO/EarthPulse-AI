"use client";

import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ForecastPoint } from "@/lib/api";

export function ForecastChart({ points, now }: { points: ForecastPoint[]; now: number }) {
  const data = points.map((p) => ({ ...p, t: p.t.slice(11, 16) }));
  return (
    <ResponsiveContainer width="100%" height={170}>
      <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -22 }}>
        <defs>
          <linearGradient id="band" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.32} />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#1B2433" strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="t" tick={{ fill: "#7C8FA6", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} axisLine={{ stroke: "#243043" }} tickLine={false} />
        <YAxis domain={[0, 1]} tick={{ fill: "#7C8FA6", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: "#10151E", border: "1px solid #243043", borderRadius: 6, fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}
          formatter={(v: number | string | (number | string)[]) => (Array.isArray(v) ? v : `${(Number(v) * 100).toFixed(0)}%`)}
        />
        <ReferenceLine y={now} stroke="#F59E0B" strokeDasharray="4 4" label={{ value: "now", fill: "#F59E0B", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} />
        <Area type="monotone" dataKey="upper" stroke="none" fill="url(#band)" />
        <Area type="monotone" dataKey="lower" stroke="none" fill="#0A0E14" />
        <Area type="monotone" dataKey="mean" stroke="#3B82F6" strokeWidth={1.6} fill="none" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
