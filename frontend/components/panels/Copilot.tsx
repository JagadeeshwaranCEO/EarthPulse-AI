"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Badge, Panel } from "@/components/ui/Panel";

const QUICK = ["Why is this risk forming?", "What should civic authorities do?", "How uncertain is this forecast?"];

export function Copilot({ riskId }: { riskId: string }) {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState("fallback");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const send = async (text: string) => {
    const content = text.trim();
    if (!content || busy) return;
    const next = [...messages, { role: "user", content }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      const res = await api.chat(next, riskId);
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
      setMode(res.llm_mode);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="AI copilot" right={<Badge tone={mode === "live" ? "green" : "slate"}>{mode === "live" ? "llm live" : "template reasoning"}</Badge>}>
      <div ref={scrollRef} className="flex h-full flex-col gap-2.5 overflow-auto p-3">
        {messages.length === 0 && (
          <div className="space-y-1.5">
            <p className="text-[11px] text-mono">
              Ask anything about the selected risk. Grounded in live telemetry; never invents sensor readings.
            </p>
            {QUICK.map((q) => (
              <button key={q} onClick={() => send(q)} className="block w-full rounded border border-edge bg-panel2 px-2.5 py-1.5 text-left text-[11px] text-slate-300 transition-colors hover:border-accent-blue/50">
                {q}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`max-w-[92%] rounded px-2.5 py-2 text-[11px] leading-relaxed ${m.role === "user" ? "self-end bg-accent-blue/15 text-slate-100" : "self-start border border-edge bg-panel2 text-slate-300"}`}>
            {m.content}
          </div>
        ))}
        {busy && <div className="telemetry text-[10px] text-mono blink">thinking…</div>}
      </div>
      <div className="flex gap-2 border-t border-edge p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder="ask about the risk, interventions, uncertainty…"
          className="telemetry flex-1 rounded border border-edge bg-panel2 px-2.5 py-1.5 text-[11px] text-slate-200 placeholder:text-mono/60 focus:border-accent-blue/60 focus:outline-none"
        />
        <button onClick={() => send(input)} disabled={busy} className="rounded border border-accent-blue/60 bg-accent-blue/10 px-3 text-[11px] font-semibold text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:opacity-40">
          send
        </button>
      </div>
    </Panel>
  );
}
