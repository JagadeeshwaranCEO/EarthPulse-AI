"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Panel } from "@/components/ui/Panel";

interface PushPublic {
  enabled: boolean;
  vapid_public_key: string | null;
  application_server: string;
}

function b64uToU8(s: string): Uint8Array {
  const pad = s.replace(/=+$/, "");
  const bin = atob(pad.replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function PushPanel() {
  const [pub, setPub] = useState<PushPublic | null>(null);
  const [count, setCount] = useState<number | null>(null);
  const [supported] = useState<boolean>(() => typeof navigator !== "undefined" && "serviceWorker" in navigator && "PushManager" in window);
  const [permission, setPermission] = useState<NotificationPermission | "unavailable">("unavailable");
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const refresh = () => {
    fetch("/api/v1/push/public").then((r) => r.json()).then(setPub).catch(() => {});
    fetch("/api/v1/push/count").then((r) => r.json()).then((d) => setCount(d.subscriptions)).catch(() => {});
  };

  const checkPermission = useCallback(async () => {
    if (!supported) return;
    setPermission(Notification.permission);
    if (Notification.permission === "granted") {
      const reg = await navigator.serviceWorker.ready.catch(() => null);
      if (reg) setSubscribed((await reg.pushManager.getSubscription()) !== null);
    }
  }, [supported]);

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (supported) void checkPermission();
  }, [supported, checkPermission]);

  const subscribe = async () => {
    if (!pub?.vapid_public_key) return;
    setBusy(true);
    setNote(null);
    try {
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== "granted") {
        setNote("notification permission not granted — push will not arrive");
        return;
      }
      const reg = await navigator.serviceWorker.register("/sw.js").catch(async () => navigator.serviceWorker.ready);
      await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: b64uToU8(pub.vapid_public_key),
      });
      const body = JSON.parse(JSON.stringify(sub));
      await fetch("/api/v1/push/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          endpoint: body.endpoint,
          p256dh: body.keys.p256dh,
          auth: body.keys.auth,
          ua: "web",
        }),
      });
      setSubscribed(true);
      setNote("registered with the push broker");
      refresh();
    } catch (e) {
      setNote(`subscribe failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const sendTest = async () => {
    setSending(true);
    setNote(null);
    try {
      const d = await fetch("/api/v1/push/test", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: "EarthPulse test", body: "Alerts are working — this is a live push." }),
      }).then((r) => r.json());
      setNote(`delivered to ${d.sent}/${d.attempted} devices`);
    } catch {
      setNote("push disabled or token missing");
    } finally {
      setSending(false);
    }
  };

  return (
    <Panel
      title="web push · offline-first alerting"
      right={
        pub ? (
          <Badge tone={pub.enabled ? "green" : "slate"}>{pub.enabled ? "push on" : "push off"}</Badge>
        ) : undefined
      }
    >
      <div className="space-y-3 p-3">
        <div className="rounded border border-edge bg-panel1 p-2.5">
          <div className="telemetry flex items-center justify-between text-[9px] uppercase tracking-widest text-mono">
            <span>device channel</span>
            <Badge tone={supported ? (subscribed ? "green" : "amber") : "slate"}>
              {!supported ? "unsupported" : subscribed ? "subscribed" : "not subscribed"}
            </Badge>
          </div>
          {pub?.enabled ? (
            <>
              <p className="mt-1.5 text-[10px] leading-relaxed text-mono">
                VAPID application server key registered. End-to-end RFC 8291 encryption, delivered over HTTP/2.
              </p>
              <button
                onClick={subscribe} disabled={busy || subscribed}
                className="mt-2 w-full rounded border border-accent-blue/60 bg-accent-blue/10 py-1.5 text-[11px] font-semibold text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "registering…" : subscribed ? "this device is registered" : "subscribe this device"}
              </button>
              <button
                onClick={sendTest} disabled={sending || count === 0}
                className="mt-1.5 w-full rounded border border-accent-green/60 bg-accent-green/10 py-1.5 text-[11px] font-semibold text-accent-green transition-colors hover:bg-accent-green/20 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {sending ? "delivering…" : `send test push (${count ?? 0} devices)`}
              </button>
            </>
          ) : (
            <p className="mt-1.5 text-[10px] text-mono">push is disabled on this deployment — set PUSH_ENABLED=true to arm the channel.</p>
          )}
          {note && <p className="telemetry mt-1.5 text-[9px] text-accent-amber">{note}</p>}
        </div>

        <div className="rounded border border-edge bg-panel1 p-2.5">
          <div className="telemetry text-[9px] uppercase tracking-widest text-mono">how it works</div>
          <ul className="mt-1.5 space-y-1 text-[10px] leading-relaxed text-mono">
            <li>· browser subscribes with your OS-level push service</li>
            <li>· server stores the subscription key material</li>
            <li>· alerts encrypt a message → HTTP/2 POST to the broker</li>
            <li>· wakes your device even if the tab is closed</li>
            <li>· offline-first PWA caches the whole command surface</li>
          </ul>
        </div>

        {permission !== "unavailable" && (
          <div className="telemetry flex gap-3 border-t border-edge pt-2 text-[9px] uppercase tracking-widest text-mono">
            <span>permission <span className="text-slate-300">{permission}</span></span>
            <span>subscriptions <span className="text-slate-300">{count ?? "—"}</span></span>
            <span>server <span className="text-slate-300">{pub?.application_server ?? "—"}</span></span>
          </div>
        )}
      </div>
    </Panel>
  );
}