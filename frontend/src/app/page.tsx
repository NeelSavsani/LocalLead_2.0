"use client";

import React, { useState, useRef } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import LeadSearchForm from "@/components/LeadSearchForm";
import LiveProgress from "@/components/LiveProgress";
import LeadTable from "@/components/LeadTable";
import ExportButton from "@/components/ExportButton";
import AppHeader from "@/components/AppHeader";

const LeadMapView = dynamic(() => import("@/components/LeadMapView"), { ssr: false });

import {
  AddToSheetResponse,
  LeadRecord,
  ScanCandidateEvent,
  ScanRequest,
  createEventSourceStream,
  startScan,
  stopScan,
} from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [isScanning, setIsScanning] = useState(false);
  const [hoveredLeadId, setHoveredLeadId] = useState<string | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [leads, setLeads] = useState<LeadRecord[]>([]);
  const [targetLimit, setTargetLimit] = useState(20);
  const [currentEvent, setCurrentEvent] = useState<ScanCandidateEvent | null>(null);
  const [logs, setLogs] = useState<ScanCandidateEvent[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; total: number } | null>(null);
  const [sheetCount, setSheetCount] = useState<number | undefined>(undefined);

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

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    try {
      const resp = await startScan(req);
      setCurrentJobId(resp.job_id);

      const es = createEventSourceStream(
        resp.job_id,
        (event) => {
          setCurrentEvent(event);
          setLogs((prev) => [...prev, event]);

          if (event.status === "QUALIFIED" && event.lead) {
            setLeads((prev) => {
              if (prev.some((item) => item.id === event.lead!.id)) {
                return prev;
              }
              return [...prev, event.lead!];
            });
          }

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

  const handleAddedToSheet = (result: AddToSheetResponse) => {
    const dup =
      result.skipped_duplicates > 0
        ? ` (${result.skipped_duplicates} duplicate${result.skipped_duplicates === 1 ? "" : "s"} skipped)`
        : "";
    setToast({
      message: `Added ${result.added_count} new lead${result.added_count === 1 ? "" : "s"}${dup}`,
      total: result.total_leads,
    });
    setSheetCount(result.total_leads);
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-900 selection:bg-emerald-500 selection:text-white">
      <AppHeader active="scanner" sheetCount={sheetCount} />

      {toast && (
        <div className="fixed bottom-6 right-6 z-[60] max-w-sm w-[calc(100%-2rem)] bg-slate-900 text-white rounded-2xl shadow-2xl border border-slate-700 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">{toast.message}</p>
              <p className="text-[11px] text-slate-400 mt-1">Sheet now has {toast.total} leads</p>
            </div>
            <button
              onClick={() => setToast(null)}
              className="text-slate-400 hover:text-white"
              aria-label="Dismiss notification"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <button
            onClick={() => router.push("/sheet")}
            className="mt-3 w-full text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-white rounded-lg py-2"
          >
            Open Sheet
          </button>
        </div>
      )}

      <main className="flex-1 w-full px-4 sm:px-6 py-6 space-y-6">
        {errorMessage && (
          <div className="bg-rose-500/10 border border-rose-500/30 text-rose-700 px-4 py-3 rounded-xl text-xs flex items-center justify-between">
            <span>{errorMessage}</span>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-rose-400 hover:text-rose-600 font-bold ml-4"
            >
              ✕
            </button>
          </div>
        )}

        <section>
          <LeadSearchForm
            onStartScan={handleStartScan}
            onStopScan={handleStopScan}
            isScanning={isScanning}
          />
        </section>

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

        {leads.length > 0 && (
          <section className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <ExportButton
                jobId={currentJobId}
                leads={leads}
                leadsCount={leads.length}
                isScanning={isScanning}
                onAddedToSheet={handleAddedToSheet}
                onAddError={(msg) => setErrorMessage(msg)}
              />
            </div>
            <div className="flex flex-col lg:flex-row gap-6">
              <div className="w-full lg:w-[58%]">
                <LeadTable 
                  leads={leads} 
                  isScanning={isScanning} 
                  onLeadHover={setHoveredLeadId} 
                  hoveredLeadId={hoveredLeadId} 
                />
              </div>
              <div className="w-full lg:w-[42%] lg:sticky lg:top-24 self-start">
                <LeadMapView leads={leads} hoveredLeadId={hoveredLeadId} />
              </div>
            </div>
          </section>
        )}
      </main>

      <footer className="border-t border-slate-200 bg-white/60 py-6 text-center text-xs text-slate-500">
        <p>
          LocalLeadPulse 2.0 • Dual-Layer Verification Engine (Maps Listing & Aggregator Blacklist Exclusion)
        </p>
      </footer>
    </div>
  );
}
