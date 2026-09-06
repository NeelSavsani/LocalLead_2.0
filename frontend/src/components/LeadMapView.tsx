"use client";

import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, LayersControl, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { LeadRecord } from "@/lib/api";
import { PhoneCall, MapPin, ExternalLink, ShieldCheck } from "lucide-react";

// Fix Leaflet's default icon path issues in Next.js
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

function MapBoundsFitter({ leads }: { leads: LeadRecord[] }) {
  const map = useMap();
  useEffect(() => {
    const validCoords = leads
      .filter((l) => l.latitude && l.longitude)
      .map((l) => [l.latitude, l.longitude] as [number, number]);
      
    if (validCoords.length > 0) {
      const bounds = L.latLngBounds(validCoords);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }, [leads, map]);
  
  return null;
}

function MapHoverFitter({ leads, hoveredLeadId }: { leads: LeadRecord[]; hoveredLeadId?: string | null }) {
  const map = useMap();
  useEffect(() => {
    if (!hoveredLeadId) return;
    const lead = leads.find((l) => l.id === hoveredLeadId);
    if (lead && lead.latitude && lead.longitude) {
      map.flyTo([lead.latitude, lead.longitude], 16, { animate: true, duration: 0.5 });
    }
  }, [hoveredLeadId, leads, map]);
  return null;
}

interface LeadMapViewProps {
  leads: LeadRecord[];
  hoveredLeadId?: string | null;
}

export default function LeadMapView({ leads, hoveredLeadId }: LeadMapViewProps) {
  const defaultCenter: [number, number] = [21.1702, 72.8311]; // Default fallback

  return (
    <div className="w-full h-[600px] rounded-xl overflow-hidden shadow-sm border border-slate-200" style={{ zIndex: 0 }}>
      <MapContainer
        center={defaultCenter}
        zoom={12}
        className="w-full h-full z-0"
        scrollWheelZoom={true}
        style={{ zIndex: 0 }}
      >
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Street (OpenStreetMap)">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>

          <LayersControl.BaseLayer name="Satellite (Esri)">
            <TileLayer
              attribution="Tiles &copy; Esri &mdash; Source: Esri"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
          </LayersControl.BaseLayer>

          <LayersControl.BaseLayer name="Terrain (OpenTopoMap)">
            <TileLayer
              attribution='Map data: &copy; OSM, SRTM | Map style: &copy; OpenTopoMap'
              url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        <MapBoundsFitter leads={leads} />
        <MapHoverFitter leads={leads} hoveredLeadId={hoveredLeadId} />

        {leads.map((lead) => {
          if (!lead.latitude || !lead.longitude) return null;
          
          return (
            <Marker key={lead.id} position={[lead.latitude, lead.longitude]}>
              <Popup className="lead-popup">
                <div className="p-1 max-w-[240px]">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide">
                      {lead.category}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[9px] font-medium text-emerald-600">
                      <ShieldCheck className="w-3 h-3" />
                      No Site
                    </span>
                  </div>
                  <h3 className="font-bold text-slate-900 text-sm mb-1 leading-tight">{lead.name}</h3>
                  <div className="flex items-start gap-1.5 text-xs text-slate-600 mb-2 mt-2">
                    <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                    <span className="leading-snug">{lead.address}</span>
                  </div>
                  {lead.phone && lead.phone !== "N/A" && (
                    <div className="flex items-center gap-1.5 text-xs font-medium text-slate-800 mb-3">
                      <PhoneCall className="w-3.5 h-3.5 text-emerald-600" />
                      <a href={`tel:${lead.phone.replace(/[^0-9+]/g, '')}`} className="hover:text-emerald-600">
                        {lead.phone}
                      </a>
                    </div>
                  )}
                  {lead.maps_url && (
                    <a
                      href={lead.maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-full flex items-center justify-center gap-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 py-1.5 rounded-lg text-xs font-semibold transition-colors"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      Open in Google Maps
                    </a>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
