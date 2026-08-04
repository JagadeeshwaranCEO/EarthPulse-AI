export interface PulseView {
  location_id: string;
  score: number;
  factors: Record<string, number>;
  recorded_at: string;
  band: "stable" | "watchful" | "stressed" | "critical";
}

export interface RiskSummary {
  location_id: string;
  location_name: string;
  region?: string;
  lat: number;
  lon: number;
  event_type: string;
  level: "low" | "moderate" | "high" | "critical";
  risk_probability: number;
  severity: number;
  confidence: number;
  trend: "rising" | "steady" | "falling";
  horizon_h: number;
  updated_at: string;
}

export interface CausalNode {
  id: string;
  label: string;
  kind: string;
  value: string;
  confidence: number;
  evidence_ids: string[];
}

export interface CausalEdge {
  source: string;
  target: string;
  label: string;
}

export interface AttributionItem {
  feature: string;
  influence: number;
  direction: "raises" | "lowers";
  description: string;
}

export interface Evidence {
  id: string;
  kind: string;
  captured_at: string;
  description: string;
  value: number | null;
  provenance: { source_id: string; source_name: string; kind: string; url: string | null; is_synthetic: boolean };
}

export interface RiskDetail extends RiskSummary {
  components: Record<string, number>;
  attribution: AttributionItem[];
  causal_chain: { nodes: CausalNode[]; edges: CausalEdge[] };
  evidence: Evidence[];
  limitations: string[];
  model_name: string;
  llm_mode: string;
  precision?: PrecisionInfo;
  crossing?: Crossing;
}

export interface PrecisionInfo {
  location_id: string;
  hazard: string;
  samples: number;
  brier: number;
  brier_skill: number;
  auc: number | null;
  climatology: number;
  calibration?: { mean_forecast: number; mean_realized: number; gap: number; sign: string };
  band_tightness: number;
  tier: "A" | "B" | "C";
}

export interface Crossing {
  location_id: string;
  hazard: string;
  high_band: { threshold: number; crossing_in_h: number | null } | null;
  moderate_band: { threshold: number; crossing_in_h: number | null } | null;
  drivers: { driver: string; label: string; current: number; stress_line: number; crosses_stress_in_h: number | null }[];
  confidence: number;
  method: string;
}

export interface LeadRung {
  lead_h: number;
  probability: number;
  level: string;
  components: Record<string, number>;
  reasons: string[];
}

export interface PredictionResponse {
  location_id: string;
  generated_at: string;
  horizon_h: number;
  probability_now: number;
  peak_probability: number;
  peak_in_h: number;
  lead_ladder: LeadRung[];
  bounds: { lower: number; upper: number };
  outlook: { day: number; horizon_h: number; mean: number; lower: number; upper: number }[];
  points: ForecastPoint[];
  model_name: string;
}

export interface ReliabilityRow {
  band: string;
  forecasts: number;
  mean_forecast: number;
  observed_fraction: number;
}

export interface ValidationReport {
  scope: string;
  generated_at: string;
  method: string;
  overall: {
    brier: number;
    brier_skill: number;
    auc: number | null;
    samples: number;
    zones: number;
    reliability: ReliabilityRow[];
    calibration: { mean_forecast: number; mean_realized: number; gap: number; sign: string };
    sharpness: number;
  };
  hazards: Record<string, { zones: number; samples: number; brier: number | null; brier_skill: number | null; tiers: Record<string, number> }>;
  zones: (PrecisionInfo & { location_name: string })[];
}

export interface ForecastPoint {
  t: string;
  mean: number;
  lower: number;
  upper: number;
}

export interface Recommendation {
  id: string;
  stakeholder: string;
  priority: number;
  action: string;
  reasoning: string;
  evidence_ids: string[];
}

export interface DebateResult {
  topic: string;
  risk_id: string;
  statements: { agent: string; position: string; evidence: string[]; confidence: number }[];
  verdict: string;
  llm_mode: string;
}

export interface SimulationResult {
  id: string;
  location_id: string;
  baseline: { probability: number; severity: number; expected_damage_usd: number; components: Record<string, number> };
  after: { probability: number; severity: number; expected_damage_usd: number; components: Record<string, number> };
  deltas: { probability_reduction: number; severity_reduction: number; damage_avoided_usd: number; damage_reduction_pct: number };
  effects: { intervention: string; intensity: number; description: string }[];
  carbon_ledger: { carbon_spent_kg: number; co2e_avoided_kg: number; net_kg: number; method: string };
}

export interface Intervention {
  id: string;
  name: string;
  description: string;
  kind: string;
  cost_index: number;
  carbon_kg: number;
}

export interface Dashboard {
  pulse: PulseView;
  alerts: { id: number; location_id: string; level: string; title: string; summary: string; raised_at: string }[];
  risks: RiskSummary[];
  crisis: boolean;
  time: string;
  tick_seconds: number;
  scope?: string;
}

export interface ResourceInventory {
  boats: number;
  pumps: number;
  shelters: number;
  budget_inr_crores: number;
  personnel: number;
}

export interface StrategyOption {
  id: string;
  title: string;
  focus: string;
  allocations: Record<string, Record<"boat" | "pump" | "shelter", number>>;
  lives_protected: number;
  economic_loss_inr_cr: number;
  co2_reduction_pct: number;
  confidence_score: number;
  is_recommended: boolean;
  rationale: string;
  actions: string[];
  execution_timeline: { time: string; label: string; phase: string; action: string }[];
}

export interface TrustScore {
  location_id: string;
  level: "High" | "Moderate" | "Low";
  score: number;
  confidence_now: number;
  sim_hour: number;
  checks: { label: string; ok: boolean; detail: string }[];
  reason: string;
}

export interface OptimizeResponse {
  inventory: ResourceInventory;
  analysis: {
    recommended_id: string;
    decision_confidence: number;
    prediction_confidence: number;
    robustness_rainfall_pct: number;
    robust_at_plus_15pct: boolean;
    fallback_strategy_id: string;
    fallback_trigger: string;
    trade_offs: Record<string, { objective: string; trade_off: string }>;
    method: string;
  };
  peak_hour: number;
  strategies: StrategyOption[];
}

export interface MemoryView {
  location_id: string;
  location_name: string;
  historical_floods_10y: number;
  known_vulnerabilities: string[];
  choke_points: string[];
  top_analogues: { event: string; date: string; severity: number; similarity: number; description: string }[];
  headline: string;
  analogue_breakdown: {
    closest_event: string;
    closest_date: string;
    similarity: number;
    matching_drivers: { driver: string; feature: string; current: number; analogue: number; matched: boolean }[];
    critical_divergences: string[];
    estimated_reliability: "High" | "Moderate" | "Low";
  } | null;
  components_now: Record<string, number>;
  provenance: { historical_events: string; is_synthetic: boolean };
}

export interface EvolutionPoint {
  hour: number;
  risk_probability: number;
  level: string;
  components: Record<string, number>;
  is_now: boolean;
}

export interface Evolution {
  location_id: string;
  now_hour: number;
  points: EvolutionPoint[];
  peak_probability: number;
  peak_at_hour: number;
  now_probability: number;
  delta_24h: number;
  generated_at: string;
}

export interface MissionBrief {
  strategy_id: string;
  title: string;
  recommended: boolean;
  markdown: string;
  facets: {
    situation: { name: string; p: number; level: string }[];
    decision: {
      decision_confidence: number | null;
      prediction_confidence: number | null;
      robustness_rainfall_pct: number | null;
      fallback_strategy_id: string | null;
      fallback_trigger: string | null;
    };
    impact_estimate: { lives_protected: number; residual_economic_exposure_inr_cr: number; co2_reduction_pct: number };
    memory: string | null;
    provenance: string;
  };
  generated_at: string;
}

export interface ScientistExplanation {
  location_id: string;
  score: number;
  model_name: string;
  formula_steps: { equation: string; explanation: string }[];
  dominant_factors: { feature: string; influence: number; weight: number; description: string }[];
  causal_chain: { nodes: CausalNode[]; edges: CausalEdge[] };
  uncertainty: { lower: number; upper: number };
  limitations: string[];
  provenance_note: string;
}

export interface CompareAnalysis {
  location_id: string;
  location_name: string;
  live: {
    risk_probability: number;
    level: string;
    severity: number;
    confidence: number;
    hour: number;
    components: Record<string, number>;
  };
  history: {
    events_10y: number;
    known_vulnerabilities: string[];
    choke_points: string[];
  };
  previous_records: { generated_at: string; risk_probability: number; severity: number }[];
  analogues: {
    event: string;
    date: string;
    severity: number;
    similarity: number;
    reliability: string;
    matching_drivers: number;
    divergence: string;
  }[];
  evolution: {
    peak_probability: number;
    peak_at_hour: number;
    delta_24h: number;
    trend: "rising" | "easing" | "steady";
  };
  verdict: { title: string; tone: "red" | "amber" | "blue"; advice: string; delta_24h: number };
  markdown: string;
  generated_at: string;
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`);
  return res.json() as Promise<T>;
}

export const api = {
  dashboard: () => j<Dashboard>("/api/v1/dashboard"),
  risks: () => j<RiskSummary[]>("/api/v1/risks"),
  risk: (id: string) => j<RiskDetail>(`/api/v1/risks/${id}`),
  prediction: (id: string) => j<PredictionResponse>(`/api/v1/risks/${id}/prediction`),
  validation: () => j<ValidationReport>(`/api/v1/validation`),
  recommendations: (id: string) => j<Recommendation[]>(`/api/v1/risks/${id}/recommendations`),
  debate: (riskId: string, force = false) =>
    j<DebateResult>(`/api/v1/agents/debate?risk_id=${riskId}${force ? "&force=true" : ""}`),
  interventions: () => j<Intervention[]>("/api/v1/simulations/interventions"),
  simulate: (location_id: string, interventions: Record<string, number>) =>
    j<SimulationResult>("/api/v1/simulations", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ location_id, event_type: "flood", interventions }),
    }),
  chat: (messages: { role: string; content: string }[], location_id: string) =>
    j<{ reply: string; llm_mode: string }>("/api/v1/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ messages, location_id }),
    }),
  setClock: (hour: number) =>
    j<{ hour: number; max: number }>(`/api/v1/sim/clock?hour=${hour}`, { method: "POST" }),
  clock: () => j<{ hour: number; max: number }>("/api/v1/sim/clock"),
  optimize: (inventory: ResourceInventory) =>
    j<OptimizeResponse>("/api/v1/decisions/optimize", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(inventory),
    }),
  memory: (locationId: string) => j<MemoryView>(`/api/v1/decisions/memory/${locationId}`),
  evolution: (locationId: string) => j<Evolution>(`/api/v1/decisions/evolution/${locationId}`),
  brief: (inventory: ResourceInventory) =>
    j<MissionBrief>("/api/v1/decisions/brief", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(inventory),
    }),
  scientist: (locationId: string) => j<ScientistExplanation>(`/api/v1/decisions/scientist/${locationId}`),
  trust: (locationId: string) => j<TrustScore>(`/api/v1/decisions/trust/${locationId}`),
  compare: (locationId: string) => j<CompareAnalysis>(`/api/v1/decisions/compare/${locationId}`),
};

export const levelColor = (level: string) =>
  level === "critical" ? "text-accent-red border-accent-red" : level === "high" ? "text-accent-amber border-accent-amber" : level === "moderate" ? "text-accent-blue border-accent-blue" : "text-accent-green border-accent-green";

export const levelFill = (level: string) =>
  level === "critical" ? "#EF4444" : level === "high" ? "#F59E0B" : level === "moderate" ? "#3B82F6" : "#10B981";
