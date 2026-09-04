"use client";

import React from "react";
import { FileSpreadsheet, Download, CheckCircle } from "lucide-react";
import { getExcelDownloadUrl } from "@/lib/api";

interface ExportButtonProps {
  jobId: string | null;
  leadsCount: number;
  isScanning: boolean;
}

export default function ExportButton({ jobId, leadsCount, isScanning }: ExportButtonProps) {
  const canDownload = Boolean(jobId && leadsCount > 0);

  const handleDownload = () => {
    if (!jobId) return;
    const url = getExcelDownloadUrl(jobId);
    window.open(url, "_blank");
  };

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-gradient-to-r from-white to-indigo-50/50 p-5 rounded-2xl border border-slate-200 shadow-xl">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
          <FileSpreadsheet className="w-6 h-6" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            Outreach-Ready Excel Workbook
            <span className="text-[11px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
              .xlsx
            </span>
          </h4>
          <p className="text-xs text-slate-500">
            Pre-configured with Dark Navy header pane, CRM Call Status dropdowns, and formatted phone links
          </p>
        </div>
      </div>

      <button
        onClick={handleDownload}
        disabled={!canDownload}
        className="w-full sm:w-auto flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white font-medium py-3 px-6 rounded-xl shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
      >
        <Download className="w-4 h-4" />
        <span>Download Excel Sheet ({leadsCount} Leads)</span>
      </button>
    </div>
  );
}
