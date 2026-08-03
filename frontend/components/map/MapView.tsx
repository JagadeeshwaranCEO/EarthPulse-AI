"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import { levelFill, type RiskSummary } from "@/lib/api";

export function MapView({ risks, selectedId, onSelect }: { risks: RiskSummary[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layersRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = L.map(container.current, { center: [13.05, 80.23], zoom: 11, zoomControl: true });
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "© OpenStreetMap © CARTO",
      maxZoom: 18,
    }).addTo(map);
    layersRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const group = layersRef.current;
    if (!map || !group) return;
    group.clearLayers();
    risks.forEach((r) => {
      const color = levelFill(r.level);
      const radius = 8 + r.risk_probability * 26;
      const ring = L.circleMarker([r.lat, r.lon], { radius, color: "#0A0E14", weight: 2, fillColor: color, fillOpacity: 0.75 });
      const halo = L.circleMarker([r.lat, r.lon], {
        radius: radius + 5,
        color, weight: 1, fill: false, opacity: 0.35, dashArray: "3 5",
      });
      const selected = r.location_id === selectedId;
      ring.bindPopup(
        `<b>${r.location_name}</b><br/>P(risk) ${(r.risk_probability * 100).toFixed(0)}% · ${r.level}<br/>conf ${(r.confidence * 100).toFixed(0)}% · sev ${r.severity.toFixed(1)}/5`
      );
      ring.on("click", () => onSelect(r.location_id));
      group.addLayer(halo);
      group.addLayer(ring);
      if (selected) {
        const sel = L.circleMarker([r.lat, r.lon], { radius: radius + 8, color, weight: 2, fillColor: color, fillOpacity: 0.15 });
        sel.addTo(group);
        map.setView([r.lat, r.lon], Math.max(map.getZoom(), 12), { animate: true });
      }
    });
  }, [risks, selectedId, onSelect]);

  return <div ref={container} className="h-full w-full" />;
}
