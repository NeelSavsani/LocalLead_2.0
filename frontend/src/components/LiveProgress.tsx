"use client";

import React from "react";
import { Activity, CheckCircle2, XCircle, Globe, MapPin, Terminal } from "lucide-react";
import { ScanCandidateEvent } from "@/lib/api";

interface LiveProgressProps {
  currentEvent: ScanCandidateEvent | null;
  qualifiedCount: number;
  targetLimit: number;
  isScanning: boolean;
  logs: ScanCandidateEvent[];
}

export default function LiveProgress({
  currentEvent,
  qualifiedCount,
  targetLimit,
  isScanning,
  logs,
}: LiveProgressProps) {
  const percentage = Math.min(100, Math.round((qualifiedCount / (targetLimit || 1)) * 100));

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "QUALIFIED":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3" />
            Qualified Lead
          </span>
        );
      case "DISQUALIFIED_MAPS":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <XCircle className="w-3 h-3" />
            Layer 1 Rejected (Has Maps Website)
          </span>
        );
      case "DISQUALIFIED_SEARCH":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <XCircle className="w-3 h-3" />
            Layer 2 Rejected (Has Search Domain)
          </span>
        );
      case "EVALUATING":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 animate-pulse">
            <Activity className="w-3 h-3 animate-spin" />
            Evaluating Candidate
          </span>
        );
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-teal-500/20 text-teal-400 border border-teal-500/30">
            <CheckCircle2 className="w-3 h-3" />
            Scan Finished
          </span>
        );
      case "STOPPED":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 font-medium">
            <XCircle className="w-3 h-3" />
            Scan Stopped
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="bg-white backdrop-blur-md border border-slate-200 rounded-2xl p-6 shadow-xl space-y-5">
      {/* Telemetry Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center">
            <Activity className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900 tracking-wide flex items-center gap-2">
              Live Two-Layer Scanning Engine
              {isScanning && (
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              )}
            </h3>
            <p className="text-xs text-slate-500">
              Dual-verification: Google Maps filter & organic search aggregator exclusion
            </p>
          </div>
        </div>

        {/* Capped Counter Pill */}
        <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-300 self-start sm:self-auto">
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">
              Verified / Limit
            </div>
            <div className="text-lg font-bold font-mono text-slate-900">
              <span className="text-emerald-600">{qualifiedCount}</span>
              <span className="text-slate-600 text-sm"> / {targetLimit}</span>
            </div>
          </div>
          <div className="w-12 h-12 rounded-full border-2 border-emerald-200 flex items-center justify-center relative">
            <span className="text-xs font-mono font-bold text-emerald-600">{percentage}%</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1.5">
        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden border border-slate-200">
          <div
            className="bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-400 h-full transition-all duration-300 ease-out rounded-full"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <div className="flex justify-between text-[11px] text-slate-500 font-mono">
          <span>Candidate Pipeline Active</span>
          <span>Target Cap: {targetLimit} Leads</span>
        </div>
      </div>

      {/* Live Activity Ticker */}
      <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-300 space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-500 border-b border-slate-300 pb-2">
          <span className="flex items-center gap-1.5 font-mono text-slate-700">
            <Terminal className="w-3.5 h-3.5 text-emerald-600" />
            Scanning Feed
          </span>
          {currentEvent && getStatusBadge(currentEvent.status)}
        </div>

        <div className="font-mono text-xs space-y-1">
          {currentEvent ? (
            <div className="text-slate-700">
              <span className="text-emerald-600 font-bold">&gt; [{currentEvent.candidate_name}]:</span>{" "}
              <span>{currentEvent.reason}</span>
            </div>
          ) : (
            <div className="text-slate-500 italic">
              &gt; Ready. Set location, category, and limit, then click &apos;Start Verification Pipeline&apos;...
            </div>
          )}
        </div>

        {/* Collapsible/Scrollable recent log stream */}
        {logs.length > 1 && (
          <div className="pt-2 border-t border-slate-300 max-h-24 overflow-y-auto space-y-1 text-[11px] font-mono text-slate-500">
            {logs.slice(-5).reverse().map((log, i) => (
              <div key={i} className="truncate">
                <span className="text-slate-400">[{log.candidate_name}]:</span>{" "}
                <span className={log.status === "QUALIFIED" ? "text-emerald-600 font-semibold" : ""}>
                  {log.reason}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
