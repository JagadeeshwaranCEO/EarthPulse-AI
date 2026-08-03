# EarthPulse AI — UI / UX Plan (Wireframes)

*Document 4/6. Covers deliverable 11.*

---

## 1. Design Language

| Element | Rule |
|---|---|
| Canvas | Dark mission-control (#0B0F14 base, #11161D panels) |
| Panels | Solid surfaces for critical data; glassmorphism (blur + 60% opacity) only for floating controls |
| Type | `JetBrains Mono` / `IBM Plex Mono` for telemetry; `Inter` / `Space Grotesk` for labels and explanations |
| Accents | Red `#FF4D4D` (crisis), Amber `#FFB020` (warning), Blue `#38BDF8` (info/water), Green `#34D399` (stable) |
| Motion | 150–300ms ease-out; subtle; crisis mode adds pulse/scan animations |
| Density | Dense but ordered — information architecture over decoration |

## 2. Screen Inventory (V1)

1. **Mission Map** — city map with ward risk overlay + live telemetry strip
2. **Risk Detail Panel** (drawer) — score, confidence meter, timeline, features
3. **Causal Chain Explorer** — D3 force/node graph of the causal chain
4. **AI Copilot** — grounded chat drawer
5. **What-If Sandbox** — intervention controls + before/after split view
6. **Crisis Command Center** — full-screen high-alert state
7. **Pulse & History** — Planet Pulse score + time-scrubber
8. **Evidence / Provenance view** — citations list + source health

## 3. Wireframe Plans (ASCII)

### 3.1 Mission Map (primary screen)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ◤ EARTHPULSE        CHENNAI ▾     [Pulse 712 ▾]  [Crisis?]  [Copilot ◍]  │  top bar
├──────────────────────────────────────────────┬───────────────────────────┤
│                                              │ ┌─ Live telemetry ──────┐ │
│   MAP (MapLibre)                             │ │ rain 24h: 186 mm  ▲  │ │
│   • wards filled by severity (amber/red)     │ │ Adyar stg: 3.2 m ▲  │ │
│   • ward 142: PULSING amber + risk chip      │ │ conf: 68% [52–81]   │ │
│   • flood overlay (animated hatch on crisis) │ │ source health: 6/6  │ │
│   • basins, river, rain cells                │ └─────────────────────┘ │
│                                              │ ┌─ Top risks ──────────┐ │
│                                              │ │ 142 flood 68% 36h ⚠ │ │
│                                              │ │ 089 flood 54% 48h   │ │
│                                              │ └─────────────────────┘ │
│   [scrubber  ◂─────────O──────────▸   now]    │                         │
├──────────────────────────────────────────────┴───────────────────────────┤
│ legend: severity ramp · horizon 24/48/72 · wards 200 · data as of 14:02  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Risk Detail Panel (drawer over map)

```
┌─ RISK: Ward 142 · Velachery ──────────────────────────────── ✕ ─┐
│  flood   68%      SEVERE ▮▮▮▮▯   in 36h        [why?] [simulate] │
│  confidence ──────────o─────────  52% ── 81% (isotonic cal.)    │
│  causal chain ▶ Rain 180mm → Chembarambakkam → Adyar 3.2m →    │
│                   saturation 74% → flood                       │
│  feature influence                                        SHAP │
│   drainage capacity     +0.19 ████████▏                        │
│   accumulated rainfall  +0.14 ██████▎                          │
│   river stage           +0.11 █████▏                           │
│  limitations: cloud cover 70% on Sentinel-1; gauge 2h stale    │
│  evidence: CWC-ADYAR-1201 · GPM-IMERG-884 · IMD-GRID-201 [3]   │
│  [open causal explorer]  [open sandbox]  [view evidence]       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Causal Chain Explorer

```
        ┌─rain 186mm/24h─┐
        └───────┬────────┘
       ┌────────┴────────┐
   ┌───┴── soil 74% sat ─┴───┐          node = card w/ value + confidence
   └───┬────────────────┬────┘          edge = arrow + strength
 ┌─────┴── Adyar 3.2m ──┴─────┐
 │   stage ↑ 0.4m/6h (95%)    │  ← click node → SHAP + evidence
 └─────┬────────────────┬────┘
       └── drainage 62% ─┘
             │
        ┌────┴────┐
        │ FLOOD   │  red node, severity chip
        └─────────┘
   [auto-layout] [lock] [export]
```

### 3.4 What-If Sandbox

```
┌─ SIMULATION: Ward 142 · event E-441 ──────────────────────────────┐
│  intervention  [pumps ▾]  [4 × 400 m³/h]  [sandbags: 2,000]      │
│  ┌─ before ────────────┐   ┌─ after ─────────────┐               │
│  │ flooded 38 ha       │   │ flooded 23 ha       │  −39%         │
│  │ affected 12.4k      │   │ affected 7.6k       │  −38%         │
│  │ damage $4.1M        │   │ damage $2.5M        │  −39%         │
│  └─────────────────────┘   └─────────────────────┘               │
│  timeline: stage ↓ by 0.9m at T+8h · flood peak moved 9h later   │
│  carbon ledger: 412 t CO₂e avoided · $1.6M losses prevented     │
│  uncertainty: ±6% (hydro model v2)    [run] [save] [audit log]   │
└──────────────────────────────────────────────────────────────────┘
```

### 3.5 Crisis Command Center (full-screen state)

```
┌────────────── CRISIS MODE · CHENNAI ── red border pulse ─────────────┐
│  WARNING  Ward 142 · SEVERE flooding in 12h · prob 82% · Δ rising  │
│  ┌ affected 18k · shelters 6 · pumps 9/12 on · evac routes 3 ──┐   │
│  map fullscreen, ward pulsing red, animated flood extent        │   │
│  operational checklist:                                          │   │
│  ☐ pre-position pumps (T-10h)  ☐ open shelter 4 (T-8h)          │   │
│  ☐ SMS evac zone A (T-6h)      ☐ road closures (T-4h)           │   │
│  [dispatch now]  [copilot briefing]  [confidence 68% 52–81 ⓘ]    │   │
└───────────────────────────────────────────────────────────────────┘
```

### 3.6 Pulse & History

```
Pulse 712/1000  ▼ 18 in 24h    components: flood 342 · air 445 ·
                                water 620 · heat 701 · fire 990
  1000│  ●─────────●────────●───────●  time-scrubber scrubs map +
  700 │       ●───────●             history in sync
  400 │  ●─●  ───────────────●──●
      └────────────────────────────  ← 7d →  → 7d →
   [what drove the drop? → causal chain + evidence]
```

## 4. Component inventory

`MapView`, `WardLayer`, `RiskChip`, `ConfidenceMeter`, `CausalGraph`, `ShapBarList`, `TimeScrubber`, `SimulationPanel`, `ChecklistCard`, `DebateView`, `PulseGauge`, `EvidenceList`, `SourceHealthBar`, `CrisisOverlay`, `CopilotDrawer`, `TelemetryStrip`.

## 5. Component → deliverable map

| Component | Blueprint requirement |
|---|---|
| CausalGraph | #1 Causal Chain Explorer |
| DebateView | #2 AI Debate Engine |
| PulseGauge + history | #3 Planet Pulse Score |
| TimeScrubber | #4 Time-Scrubbing Digital Twin |
| SimulationPanel | #5 What-If Sandbox |
| ShapBarList | #6 SHAP Transparency Pane |
| CrisisOverlay | #7 Crisis Command Center |
| CarbonLedger readout | #8 Carbon Impact Ledger |

---

*Next: docs/05-roadmap.md*
