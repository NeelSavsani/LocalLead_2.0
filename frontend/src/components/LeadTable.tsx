"use client";

import React from "react";
import { Phone, MapPin, ExternalLink, ShieldCheck, Sparkles, Building2 } from "lucide-react";
import { LeadRecord } from "@/lib/api";

interface LeadTableProps {
  leads: LeadRecord[];
  isScanning: boolean;
}

export default function LeadTable({ leads, isScanning }: LeadTableProps) {
  if (leads.length === 0) {
    return (
      <div className="bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-2xl p-12 text-center shadow-xl">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4">
          <Building2 className="w-8 h-8" />
        </div>
        <h3 className="text-base font-semibold text-white mb-1">No Verified Leads Collected Yet</h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          {isScanning
            ? "Evaluating candidates through the dual-layer filter... Qualified leads will stream here in real-time."
            : "Select a location, category, and limit above, then click 'Start Verification Pipeline' to discover local businesses without official websites."}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
      <div className="p-4 sm:p-6 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white tracking-wide flex items-center gap-2">
            Verified Qualified Leads
            <span className="bg-emerald-500/10 text-emerald-400 text-xs px-2.5 py-0.5 rounded-full border border-emerald-500/30 font-mono">
              {leads.length} Leads
            </span>
          </h3>
          <p className="text-xs text-slate-400">
            Confirmed: No standalone website on Google Maps or organic search engines
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
              <th className="py-3.5 px-4 font-mono w-20">ID</th>
              <th className="py-3.5 px-4">Business Name</th>
              <th className="py-3.5 px-4">Category</th>
              <th className="py-3.5 px-4">Phone</th>
              <th className="py-3.5 px-4">Address / Area</th>
              <th className="py-3.5 px-4">Pitch Angle</th>
              <th className="py-3.5 px-4">Verification</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {leads.map((lead, idx) => (
              <tr
                key={lead.id || idx}
                className="hover:bg-slate-800/40 transition-colors group"
              >
                <td className="py-3.5 px-4 font-mono font-medium text-slate-400">
                  {lead.id}
                </td>
                <td className="py-3.5 px-4">
                  <div className="font-semibold text-white text-sm group-hover:text-indigo-300 transition-colors">
                    {lead.name}
                  </div>
                  {lead.maps_url && (
                    <a
                      href={lead.maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 mt-0.5"
                    >
                      <span>View on Google Maps</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  )}
                </td>
                <td className="py-3.5 px-4">
                  <span className="bg-indigo-500/15 text-indigo-300 px-2.5 py-1 rounded-lg border border-indigo-500/30 text-[11px] font-medium">
                    {lead.category}
                  </span>
                </td>
                <td className="py-3.5 px-4 whitespace-nowrap">
                  {lead.phone && lead.phone !== "N/A" ? (
                    <a
                      href={`tel:${lead.phone.replace(/[^0-9+]/g, "")}`}
                      className="inline-flex items-center gap-1.5 font-mono font-medium text-emerald-400 hover:text-emerald-300 bg-emerald-950/40 px-2 py-1 rounded border border-emerald-800/40"
                    >
                      <Phone className="w-3 h-3" />
                      {lead.phone}
                    </a>
                  ) : (
                    <span className="text-slate-500 italic">No phone listed</span>
                  )}
                </td>
                <td className="py-3.5 px-4 max-w-xs truncate text-slate-300">
                  <div className="truncate" title={lead.address}>
                    {lead.address}
                  </div>
                  {lead.area && (
                    <span className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                      <MapPin className="w-2.5 h-2.5 text-indigo-400 shrink-0" />
                      {lead.area}
                    </span>
                  )}
                </td>
                <td className="py-3.5 px-4 max-w-xs text-slate-300">
                  <div className="flex items-center gap-1.5 text-slate-200">
                    <Sparkles className="w-3 h-3 text-amber-400 shrink-0" />
                    <span className="text-[11px]">{lead.pitch_angle}</span>
                  </div>
                </td>
                <td className="py-3.5 px-4 whitespace-nowrap">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-medium">
                    <ShieldCheck className="w-3 h-3" />
                    No Website Found
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
