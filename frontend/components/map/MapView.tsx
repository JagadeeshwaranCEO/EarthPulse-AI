"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { levelFill, type RiskSummary } from "@/lib/api";

type BaseKey = "esri" | "nasa" | "ops";

interface BaseDef {
  label: string;
  nasa?: boolean;
}

const BASES: Record<BaseKey, BaseDef> = {
  esri: { label: "esri satellite · max-res" },
  nasa: { label: "nasa modis true color", nasa: true },
  ops: { label: "ops vector dark" },
};

const GIBS_MATRIX = "GoogleMapsCompatible_Level9";
// sample tile covering the Tamil Nadu theatre, used to probe which archived day is live
const SAMPLE_TILE = { z: 7, x: 92, y: 59 };
const MODIS_NASA_ZOOM = 14; // upscaled beyond native level 9 for a crisp pull-in

function recentDays(n = 9): string[] {
  const out: string[] = [];
  for (let i = 0; i < n; i++) {
    const d = new Date(Date.now() - i * 86400000);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

async function resolveNasaDay(layer: "MODIS_Terra_CorrectedReflectance_TrueColor" | "VIIRS_NOAA20_CorrectedReflectance_TrueColor_Granule"): Promise<string | null> {
  const fmt = layer === "MODIS_Terra_CorrectedReflectance_TrueColor" ? "jpg" : "png";
  for (const day of recentDays()) {
    const url = `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${day}/${GIBS_MATRIX}/${SAMPLE_TILE.z}/${SAMPLE_TILE.x}/${SAMPLE_TILE.y}.${fmt}`;
    try {
      const res = await fetch(url, { method: "GET" });
      if (res.ok) return day;
    } catch {
      /* keep probing */
    }
  }
  return null;
}

function gibsTile(day: string) {
  return (layer: "MODIS_Terra_CorrectedReflectance_TrueColor" | "VIIRS_NOAA20_CorrectedReflectance_TrueColor_Granule") => {
    const fmt = layer === "MODIS_Terra_CorrectedReflectance_TrueColor" ? "jpeg" : "png";
    return L.tileLayer(
      `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${day}/${GIBS_MATRIX}/{z}/{y}/{x}.${fmt}`,
      { attribution: "NASA GIBS / Worldview", maxZoom: MODIS_NASA_ZOOM, maxNativeZoom: 9, opacity: 0.85 },
    );
  };
}

function LabelsLayer() {
  return L.tileLayer("https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png", {
    attribution: "© OpenStreetMap © CARTO",
    maxZoom: 20,
  });
}

function popupHtml(r: RiskSummary) {
  const dot = levelFill(r.level);
  return (
    `<div style="font: 11px ui-monospace, monospace; min-width: 200px">` +
    `<div style="display:flex; align-items:center; gap:6px">` +
    `<span style="width:8px; height:8px; border-radius:9999px; background:${dot}; box-shadow:0 0 6px ${dot}"></span>` +
    `<span style="font-weight:600; font-size:12px; color:#e2e8f0">${r.location_name}</span></div>` +
    `<div style="margin-top:6px; display:flex; align-items:center; gap:8px">` +
    `<div style="flex:1; height:5px; background:#1e293b; border-radius:9999px; overflow:hidden"><div style="width:${(r.risk_probability * 100).toFixed(0)}%; height:100%; background:${dot}"></div></div>` +
    `<span style="color:#e2e8f0; font-weight:600">${(r.risk_probability * 100).toFixed(0)}%</span></div>` +
    `<div style="color:#7c8fa6">${r.level} · conf ${(r.confidence * 100).toFixed(0)}% · sev ${r.severity.toFixed(1)}/5 · ${r.trend}</div>` +
    `<div style="margin-top:2px; color:#526070">${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}</div>` +
    `</div>`
  );
}

export function MapView({ risks, selectedId, onSelect }: { risks: RiskSummary[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseRef = useRef<L.TileLayer | null>(null);
  const labelsRef = useRef<L.TileLayer | null>(null);
  const viirsRef = useRef<L.TileLayer | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const boundsKeyRef = useRef<string>("");
  const lastSelRef = useRef<string | null>(null);
  const [base, setBase] = useState<BaseKey>("esri");
  const [viiirs, setViiirs] = useState(false);
  const [nasaDay, setNasaDay] = useState<string | null>(null);
  const [fitTick, setFitTick] = useState(0);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = L.map(container.current, {
      center: [10.7, 78.8],
      zoom: 7,
      zoomControl: true,
      zoomSnap: 0.5,
      zoomDelta: 0.5,
      wheelPxPerZoomLevel: 90,
    });
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);
    baseRef.current = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 20, attribution: "© Esri, Maxar, Earthstar Geographics, USDA, USGS" },
    ).addTo(map);
    labelsRef.current = LabelsLayer().addTo(map);
    markersRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    resolveNasaDay("MODIS_Terra_CorrectedReflectance_TrueColor").then((d) => alive && setNasaDay(d));
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (baseRef.current) map.removeLayer(baseRef.current);
    if (base === "nasa") {
      const day = nasaDay ?? recentDays(9).at(-1)!;
      baseRef.current = gibsTile(day)("MODIS_Terra_CorrectedReflectance_TrueColor").addTo(map);
    } else if (base === "ops") {
      baseRef.current = L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        { maxZoom: 18, attribution: "© OpenStreetMap © CARTO" },
      ).addTo(map);
    } else {
      baseRef.current = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 20, attribution: "© Esri, Maxar, Earthstar Geographics, USDA, USGS" },
      ).addTo(map);
    }
    if (labelsRef.current) labelsRef.current.setOpacity(base === "ops" ? 0 : 1);
  }, [base, nasaDay]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (viirsRef.current) map.removeLayer(viirsRef.current);
    viirsRef.current = null;
    if (viiirs && nasaDay) {
      viirsRef.current = gibsTile(nasaDay)("VIIRS_NOAA20_CorrectedReflectance_TrueColor_Granule").setOpacity(0.7).addTo(map);
    }
  }, [viiirs, nasaDay]);

  useEffect(() => {
    const map = mapRef.current;
    const group = markersRef.current;
    if (!map || !group) return;
    group.clearLayers();
    if (risks.length > 0) {
      const lats = risks.map((r) => r.lat);
      const lons = risks.map((r) => r.lon);
      const key = `${Math.min(...lats).toFixed(2)},${Math.min(...lons).toFixed(2)},${Math.max(...lats).toFixed(2)},${Math.max(...lons).toFixed(2)}`;
      if (key !== boundsKeyRef.current || fitTick > 0) {
        boundsKeyRef.current = key;
        const sw: L.LatLngTuple = [Math.min(...lats), Math.min(...lons)];
        const ne: L.LatLngTuple = [Math.max(...lats), Math.max(...lons)];
        map.fitBounds(new L.LatLngBounds(sw, ne).pad(0.12), { animate: true, maxZoom: 10 });
      }
    }
    risks.forEach((r) => {
      const color = levelFill(r.level);
      const isHot = r.level === "critical" || r.level === "high";
      const radius = Math.max(5, 8 + r.risk_probability * 26 + (r.severity - 3) * 2);
      const ring = L.circleMarker([r.lat, r.lon], { radius, color: "#FFFFFF", weight: 1.5, fillColor: color, fillOpacity: 0.85, className: isHot ? "risk-pulse" : "" });
      const halo = L.circleMarker([r.lat, r.lon], { radius: radius + 5, color, weight: 1, fill: false, opacity: isHot ? 0.55 : 0.4, dashArray: "3 5", className: isHot ? "risk-pulse-halo" : "" });
      const selected = r.location_id === selectedId;
      ring.bindPopup(popupHtml(r), { closeButton: false });
      ring.bindTooltip(`${r.location_name} · ${(r.risk_probability * 100).toFixed(0)}%`, { direction: "top", offset: [0, -radius], opacity: 0.95 });
      ring.on("click", () => onSelect(r.location_id));
      group.addLayer(halo);
      group.addLayer(ring);
      if (selected) {
        const sel = L.circleMarker([r.lat, r.lon], { radius: radius + 9, color, weight: 2, fillColor: color, fillOpacity: 0.15, className: "risk-selected" });
        sel.bindTooltip(`${r.location_name} · selected`, { permanent: true, direction: "top", offset: [0, -radius - 9], className: "risk-selected-tip" });
        sel.addTo(group);
        // Center only when the selection actually changed AND the zone is off-screen —
        // never re-snap on every WS tick (that is what made zoom-out impossible).
        if (selected && lastSelRef.current !== r.location_id) {
          lastSelRef.current = r.location_id;
          if (!map.getBounds().contains([r.lat, r.lon])) {
            map.setView([r.lat, r.lon], Math.max(map.getZoom(), 8), { animate: true });
          }
        }
      }
    });
  }, [risks, selectedId, onSelect, fitTick]);

  return (
    <div className="relative h-full w-full">
      <div ref={container} className="h-full w-full" />
      <div className="absolute bottom-3 left-3 z-[500] rounded border border-edge bg-panel/90 p-2 backdrop-blur-sm">
        <div className="telemetry mb-1 text-[9px] uppercase tracking-widest text-mono">risk level</div>
        <div className="space-y-0.5">
          {[{ l: "critical", c: "#EF4444" }, { l: "high", c: "#F59E0B" }, { l: "moderate", c: "#3B82F6" }, { l: "low", c: "#22C55E" }].map((x) => (
            <div key={x.l} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: x.c, boxShadow: `0 0 6px ${x.c}` }} />
              <span className="telemetry text-[9px] text-slate-300">{x.l}</span>
            </div>
          ))}
        </div>
        <div className="telemetry mt-1 text-[8px] uppercase tracking-wider text-mono/60">size ∝ P(risk)</div>
      </div>
      <div className="absolute right-2 top-14 z-[500] flex flex-col gap-1 rounded border border-edge bg-panel/90 p-1 backdrop-blur-sm">
        {(Object.keys(BASES) as BaseKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setBase(k)}
            className={`telemetry rounded px-2 py-1 text-left text-[9px] uppercase tracking-widest ${base === k ? "bg-accent-blue/25 text-accent-blue" : "text-mono hover:bg-panel2"}`}
          >
            {BASES[k].label}
          </button>
        ))}
        <button
          onClick={() => setViiirs(!viiirs)}
          className={`telemetry mt-1 rounded border-t border-edge px-2 py-1 text-left text-[9px] uppercase tracking-widest ${viiirs ? "bg-accent-red/25 text-accent-red" : "text-mono hover:bg-panel2"}`}
        >
          {viiirs ? "●" : "○"} nasa viirs analysis
        </button>
        <button
          onClick={() => setFitTick((t) => t + 1)}
          className="telemetry mt-1 rounded border-t border-edge px-2 py-1 text-left text-[9px] uppercase tracking-widest text-mono hover:bg-panel2"
        >
          ⤢ fit theatre
        </button>
      </div>
    </div>
  );
}