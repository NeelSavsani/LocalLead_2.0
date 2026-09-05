"use client";

import React, { useState, useRef } from "react";
import {
  Radar,
  Sparkles,
  PhoneCall,
  LayoutDashboard,
  ShieldCheck,
  CheckCircle2,
  FileSpreadsheet,
} from "lucide-react";
import LeadSearchForm from "@/components/LeadSearchForm";
import LiveProgress from "@/components/LiveProgress";
import LeadTable from "@/components/LeadTable";
import ExportButton from "@/components/ExportButton";
import {
  LeadRecord,
  ScanCandidateEvent,
  ScanRequest,
  createEventSourceStream,
  startScan,
  stopScan,
} from "@/lib/api";

export default function DashboardPage() {
  const [isScanning, setIsScanning] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [leads, setLeads] = useState<LeadRecord[]>([]);
  const [targetLimit, setTargetLimit] = useState(20);
  const [currentEvent, setCurrentEvent] = useState<ScanCandidateEvent | null>(null);
  const [logs, setLogs] = useState<ScanCandidateEvent[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  const handleStopScan = async () => {
    if (currentJobId) {
      try {
        await stopScan(currentJobId);
      } catch (err) {
        console.warn("Error requesting stop scan:", err);
      }
    }
    setIsScanning(false);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  const handleStartScan = async (req: ScanRequest) => {
    setErrorMessage(null);
    setLeads([]);
    setLogs([]);
    setCurrentEvent(null);
    setTargetLimit(req.limit);
    setIsScanning(true);

    // Close any previous stream
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    try {
      const resp = await startScan(req);
      setCurrentJobId(resp.job_id);

      // Connect to real-time Server-Sent Events stream
      const es = createEventSourceStream(
        resp.job_id,
        (event) => {
          setCurrentEvent(event);
          setLogs((prev) => [...prev, event]);

          // Append qualified lead to list in real-time
          if (event.status === "QUALIFIED" && event.lead) {
            setLeads((prev) => {
              // Ensure uniqueness by ID
              if (prev.some((item) => item.id === event.lead!.id)) {
                return prev;
              }
              return [...prev, event.lead!];
            });
          }

          // Terminate scan if finished, stopped, or target limit reached
          if (
            event.status === "COMPLETED" ||
            event.status === "STOPPED" ||
            event.event === "scan_stopped" ||
            event.qualified_count >= req.limit
          ) {
            setIsScanning(false);
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }
          }
        },
        (err) => {
          console.warn("SSE connection closed or completed:", err);
          setIsScanning(false);
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
          }
        }
      );

      eventSourceRef.current = es;
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to initiate lead verification scan.");
      setIsScanning(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-900 selection:bg-emerald-500 selection:text-white">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 bg-white backdrop-blur-lg border-b border-slate-200 w-full">
        <div className="w-full px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-emerald-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Radar className="w-5 h-5 text-white animate-subtle" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base tracking-tight text-slate-900">LocalLeadPulse</span>
                <span className="text-[10px] uppercase font-mono font-bold bg-emerald-500/10 text-emerald-600 px-1.5 py-0.5 rounded border border-emerald-500/20">
                  v2.0
                </span>
              </div>
              <p className="text-[11px] text-slate-500 hidden sm:block">
                Two-Layer Verified B2B Lead Engine for Local Businesses Without Websites
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-2">
            <button
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all bg-emerald-50 text-emerald-700 border border-emerald-200"
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span>Lead Scanner</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area - Full Width */}
      <main className="flex-1 w-full px-4 sm:px-6 py-6 space-y-6">
        {/* Error Alert if any */}
        {errorMessage && (
          <div className="bg-rose-500/10 border border-rose-500/30 text-rose-300 px-4 py-3 rounded-xl text-xs flex items-center justify-between">
            <span>{errorMessage}</span>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-rose-400 hover:text-rose-200 font-bold ml-4"
            >
              ✕
            </button>
          </div>
        )}

        {/* Lead Search Input Console */}
        <section>
          <LeadSearchForm
            onStartScan={handleStartScan}
            onStopScan={handleStopScan}
            isScanning={isScanning}
          />
        </section>

        {/* Live Progress & Candidate Telemetry */}
        {(isScanning || logs.length > 0) && (
          <section>
            <LiveProgress
              currentEvent={currentEvent}
              qualifiedCount={leads.length}
              targetLimit={targetLimit}
              isScanning={isScanning}
              logs={logs}
            />
          </section>
        )}

        {/* Excel Download Action Bar */}
        {leads.length > 0 && (
          <section>
            <ExportButton
              jobId={currentJobId}
              leadsCount={leads.length}
              isScanning={isScanning}
            />
          </section>
        )}

        {/* Leads Table */}
        <section>
          <LeadTable leads={leads} isScanning={isScanning} />
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white/60 py-6 text-center text-xs text-slate-500">
        <p>
          LocalLeadPulse 2.0 • Dual-Layer Verification Engine (Maps Listing & Aggregator Blacklist Exclusion)
        </p>
      </footer>
    </div>
  );
}
