# 07 — UI Wireframe Plan

Design language: dark mission-control canvas (`#0A0E14`), dense-but-clean panels,
solid surfaces for critical data, glassmorphism only on floating controls,
monospace for telemetry (`JetBrains Mono`), geometric sans for labels
(`Inter`), semantic accents **red / amber / blue**, smooth 200–300ms motion.

## Screens

```
┌──────────────────────────────────────────────────────────────────┐
│ CRISIS BANNER  (red, only when severity >= 3)                     │
├───────────────┬──────────────────────────────────────────────────┤
│ LEFT RAIL     │  CENTER: MAP (leaflet)                           │
│ · Pulse 0-1000│  risk circles · time scrubber (bottom)           │
│ · Alert list  │  hover → popup summary                           │
│ · Agent status├──────────────────────────────────────────────────┤
│ · Tabs        │  RIGHT PANEL (contextual, 380px)                 │
│               │  risk detail · causal chain · attribution ·      │
│               │  evidence · copilot · debate                     │
└───────────────┴──────────────────────────────────────────────────┘
```

Tabs in right panel: **Detail · Causal · Simulate · Agents · Copilot**.
Crisis mode: red ambient glow, banner, alert ticker, heartbeat indicator.
