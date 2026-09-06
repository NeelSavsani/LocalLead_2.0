"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { LayoutDashboard, Radar, Table2 } from "lucide-react";
import { getSheetLeads } from "@/lib/api";

interface AppHeaderProps {
  active: "scanner" | "sheet";
  sheetCount?: number;
}

export default function AppHeader({ active, sheetCount }: AppHeaderProps) {
  const [total, setTotal] = useState(sheetCount ?? 0);

  useEffect(() => {
    if (typeof sheetCount === "number") {
      setTotal(sheetCount);
      return;
    }
    getSheetLeads()
      .then((data) => setTotal(data.total_leads))
      .catch(() => undefined);
  }, [sheetCount]);

  return (
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

        <div className="flex items-center gap-2">
          <Link
            href="/"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
              active === "scanner"
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-white text-slate-600 border-slate-200 hover:border-emerald-200 hover:text-emerald-700"
            }`}
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            <span>Lead Scanner</span>
          </Link>
          <Link
            href="/sheet"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
              active === "sheet"
                ? "bg-slate-900 text-white border-slate-800"
                : "bg-white text-slate-600 border-slate-200 hover:border-slate-400 hover:text-slate-900"
            }`}
          >
            <Table2 className="w-3.5 h-3.5" />
            <span>Sheet Workspace ({total})</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
