"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Dashboard } from "@/lib/api";

/** Live mission-control state: WS ticker with REST fallback polling. */
export function useMissionControl() {
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [wsLive, setWsLive] = useState(false);
  const [clock, setClock] = useState<{ hour: number; max: number } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const scopeRef = useRef<string>("chennai");

  const refresh = useCallback(async () => {
    try {
      const d = await api.dashboard();
      scopeRef.current = d.scope ?? "chennai";
      setDash(d);
    } catch {
      /* backend warming up */
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";
    const apiOrigin = apiBase.startsWith("http")
      ? apiBase
      : typeof window !== "undefined"
        ? window.location.origin
        : "";
    const proto = apiOrigin.startsWith("https") ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${apiOrigin.replace(/^https?:\/\//, "")}/ws`);
    wsRef.current = ws;
    ws.onopen = () => {
      setWsLive(true);
      refresh();
    };
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "tick" && msg.pulse) {
        setDash({ pulse: msg.pulse, alerts: msg.alerts, risks: msg.top_risks, crisis: msg.crisis, time: msg.time, tick_seconds: msg.tick_seconds, scope: scopeRef.current });
        setWsLive(true);
      }
    };
    ws.onclose = () => {
      setWsLive(false);
      setTimeout(connect, 3000);
    };
    ws.onerror = () => ws.close();
  }, [refresh]);

  useEffect(() => {
    connect();
    api.clock().then(setClock).catch(() => {});
    const poll = setInterval(() => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) refresh();
    }, 8000);
    return () => {
      clearInterval(poll);
      wsRef.current?.close();
    };
  }, [connect, refresh]);

  const scrub = useCallback(async (hour: number) => {
    const next = await api.setClock(Math.round(hour));
    setClock(next);
    await refresh();
  }, [refresh]);

  return { dash, wsLive, clock, scrub, refresh };
}
