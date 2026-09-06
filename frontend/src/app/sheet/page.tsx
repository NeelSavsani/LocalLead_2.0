"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Phone,
  Search,
  Trash2,
} from "lucide-react";
import AppHeader from "@/components/AppHeader";
import {
  CALL_STATUS_OPTIONS,
  SheetLeadRecord,
  deleteSheetLead,
  getSheetExcelDownloadUrl,
  getSheetLeads,
  updateSheetLead,
} from "@/lib/api";

const PAGE_SIZES = [10, 25, 50, 100];
const CALL_FILTERS = ["All", "Pending", "Interested", "Not Interested", "Not Reachable", "Other"];

type SortKey =
  | "id"
  | "name"
  | "category"
  | "phone"
  | "address"
  | "area"
  | "verification_status"
  | "call_status"
  | "date_identified";

function statusTone(status: string): string {
  switch (status) {
    case "Interested":
      return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    case "Not Interested":
      return "bg-rose-500/15 text-rose-300 border-rose-500/30";
    case "Not Reachable":
      return "bg-amber-500/15 text-amber-300 border-amber-500/30";
    case "Other":
      return "bg-sky-500/15 text-sky-300 border-sky-500/30";
    default:
      return "bg-slate-700/80 text-slate-200 border-slate-600";
  }
}

export default function SheetWorkspacePage() {
  const [leads, setLeads] = useState<SheetLeadRecord[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [totalLeads, setTotalLeads] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [callStatus, setCallStatus] = useState("All");
  const [sortKey, setSortKey] = useState<SortKey>("id");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const loadSheet = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSheetLeads();
      setLeads(data.leads);
      setCategories(data.categories);
      setTotalLeads(data.total_leads);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load sheet workspace");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSheet();
  }, [loadSheet]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return leads.filter((lead) => {
      if (category !== "All" && lead.category !== category) return false;
      if (callStatus !== "All" && lead.call_status !== callStatus) return false;
      if (!q) return true;
      const hay = [lead.name, lead.phone, lead.address, lead.area, lead.id]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [leads, search, category, callStatus]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = String(a[sortKey] ?? "").toLowerCase();
      const bv = String(b[sortKey] ?? "").toLowerCase();
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pageRows = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const showingFrom = sorted.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const showingTo = Math.min(currentPage * pageSize, sorted.length);

  useEffect(() => {
    setPage(1);
  }, [search, category, callStatus, pageSize]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const SortIcon = ({ column }: { column: SortKey }) => {
    if (sortKey !== column) return <ArrowUpDown className="w-3 h-3 opacity-40" />;
    return sortDir === "asc" ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />;
  };

  const handleStatusChange = async (leadId: string, nextStatus: string) => {
    const previous = leads;
    setLeads((curr) => curr.map((row) => (row.id === leadId ? { ...row, call_status: nextStatus } : row)));
    try {
      const updated = await updateSheetLead(leadId, { call_status: nextStatus });
      setLeads((curr) => curr.map((row) => (row.id === leadId ? { ...row, ...updated } : row)));
    } catch (err: any) {
      setLeads(previous);
      setError(err.message || "Failed to update call status");
    }
  };

  const handleDelete = async (leadId: string) => {
    const previous = leads;
    setLeads((curr) => curr.filter((row) => row.id !== leadId));
    try {
      await deleteSheetLead(leadId);
      setTotalLeads((n) => Math.max(0, n - 1));
    } catch (err: any) {
      setLeads(previous);
      setError(err.message || "Failed to delete lead");
    }
  };

  const pageNumbers = useMemo(() => {
    const windowSize = 5;
    let start = Math.max(1, currentPage - 2);
    let end = Math.min(pageCount, start + windowSize - 1);
    start = Math.max(1, end - windowSize + 1);
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  }, [currentPage, pageCount]);

  const thClass =
    "py-3 px-3 text-[11px] uppercase tracking-wider font-semibold text-slate-400 whitespace-nowrap cursor-pointer select-none hover:text-white";

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      <AppHeader active="sheet" sheetCount={totalLeads} />

      <main className="flex-1 w-full px-4 sm:px-6 py-6 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">Sheet Workspace</h1>
            <p className="text-xs text-slate-500 mt-1">
              Persistent master list with phone / Maps URL deduplication. Existing call status is never overwritten.
            </p>
          </div>
          <button
            onClick={() => window.open(getSheetExcelDownloadUrl(), "_blank")}
            className="inline-flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-lg shadow-emerald-900/40"
          >
            <Download className="w-4 h-4" />
            Export to Excel
          </button>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-4 flex flex-col xl:flex-row gap-3 xl:items-center shadow-sm">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, phone, address, or landmark…"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-900 min-w-[160px]"
          >
            <option value="All">All categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
          <select
            value={callStatus}
            onChange={(e) => setCallStatus(e.target.value)}
            className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-900 min-w-[180px]"
          >
            {CALL_FILTERS.map((opt) => (
              <option key={opt} value={opt}>
                {opt === "All" ? "All call statuses" : opt}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <div className="bg-rose-500/10 border border-rose-500/30 text-rose-200 px-4 py-3 rounded-xl text-xs">
            {error}
          </div>
        )}

        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs min-w-[1100px]">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className={thClass} onClick={() => toggleSort("id")}>
                    <span className="inline-flex items-center gap-1">ID <SortIcon column="id" /></span>
                  </th>
                  <th className={thClass} onClick={() => toggleSort("name")}>
                    <span className="inline-flex items-center gap-1">Business Name <SortIcon column="name" /></span>
                  </th>
                  <th className={thClass} onClick={() => toggleSort("category")}>
                    <span className="inline-flex items-center gap-1">Category <SortIcon column="category" /></span>
                  </th>
                  <th className={thClass} onClick={() => toggleSort("phone")}>
                    <span className="inline-flex items-center gap-1">Phone <SortIcon column="phone" /></span>
                  </th>
                  <th className={thClass} onClick={() => toggleSort("address")}>
                    <span className="inline-flex items-center gap-1">Physical Address <SortIcon column="address" /></span>
                  </th>
                  <th className={thClass} onClick={() => toggleSort("area")}>
                    <span className="inline-flex items-center gap-1">Area <SortIcon column="area" /></span>
                  </th>
                  <th className="py-3 px-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500 whitespace-nowrap">
                    Google Map
                  </th>
                  <th className={thClass} onClick={() => toggleSort("verification_status")}>
                    <span className="inline-flex items-center gap-1">Verification <SortIcon column="verification_status" /></span>
                  </th>
                  <th className={thClass} onClick={() => toggleSort("call_status")}>
                    <span className="inline-flex items-center gap-1">Call Status <SortIcon column="call_status" /></span>
                  </th>
                  <th className={thClass} onClick={() => toggleSort("date_identified")}>
                    <span className="inline-flex items-center gap-1">Date <SortIcon column="date_identified" /></span>
                  </th>
                  <th className="py-3 px-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading && (
                  <tr>
                    <td colSpan={11} className="py-16 text-center text-slate-500">
                      Loading sheet…
                    </td>
                  </tr>
                )}
                {!loading && pageRows.length === 0 && (
                  <tr>
                    <td colSpan={11} className="py-16 text-center text-slate-500">
                      No leads in the sheet yet. Run a scan and click “+ Add to Sheet”.
                    </td>
                  </tr>
                )}
                {pageRows.map((lead, idx) => (
                  <tr key={lead.id} className={idx % 2 === 1 ? "bg-slate-50/50" : "bg-white hover:bg-slate-50"}>
                    <td className="py-3 px-3 font-mono text-slate-500 whitespace-nowrap">{lead.id}</td>
                    <td className="py-3 px-3 font-semibold text-slate-900 min-w-[180px]">{lead.name}</td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className="px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {lead.category}
                      </span>
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      {lead.phone && lead.phone !== "N/A" ? (
                        <a
                          href={`tel:${lead.phone.replace(/[^0-9+]/g, "")}`}
                          className="inline-flex items-center gap-1.5 font-mono text-emerald-300 hover:text-emerald-200"
                        >
                          <Phone className="w-3 h-3" />
                          {lead.phone}
                        </a>
                      ) : (
                        <span className="text-slate-500 italic">N/A</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-600 max-w-xs">
                      <div className="truncate" title={lead.address}>
                        {lead.address}
                      </div>
                    </td>
                    <td className="py-3 px-3 text-slate-600 whitespace-nowrap">{lead.area || "—"}</td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      {lead.maps_url ? (
                        <a
                          href={lead.maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-emerald-600 hover:text-emerald-500"
                        >
                          Open Google Map
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-500 max-w-[180px]">
                      <span className="line-clamp-2">{lead.verification_status}</span>
                    </td>
                    <td className="py-3 px-3">
                      <select
                        value={lead.call_status}
                        onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                        className={`rounded-lg border px-2 py-1.5 text-[11px] font-medium ${statusTone(lead.call_status)} bg-white`}
                      >
                        {CALL_STATUS_OPTIONS.map((opt) => (
                          <option key={opt} value={opt} className="bg-white text-slate-900">
                            {opt}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 px-3 text-slate-500 whitespace-nowrap">{lead.date_identified}</td>
                    <td className="py-3 px-3">
                      <button
                        onClick={() => handleDelete(lead.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                        aria-label={`Remove ${lead.name}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 px-4 py-3 border-t border-slate-200 bg-slate-50">
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <label className="flex items-center gap-2">
                Rows per page
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  className="bg-white border border-slate-300 rounded-lg px-2 py-1 text-slate-700"
                >
                  {PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
              <span>
                Showing {showingFrom} to {showingTo} of {sorted.length} leads
              </span>
            </div>
            <div className="flex items-center gap-1">
              <button
                disabled={currentPage <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2 py-1.5 rounded-lg border border-slate-300 text-slate-600 disabled:opacity-30 hover:bg-slate-100"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              {pageNumbers.map((num) => (
                <button
                  key={num}
                  onClick={() => setPage(num)}
                  className={`min-w-[32px] px-2 py-1.5 rounded-lg text-xs font-semibold border ${
                    num === currentPage
                      ? "bg-emerald-600 border-emerald-500 text-white"
                      : "border-slate-300 text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {num}
                </button>
              ))}
              <button
                disabled={currentPage >= pageCount}
                onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                className="px-2 py-1.5 rounded-lg border border-slate-300 text-slate-600 disabled:opacity-30 hover:bg-slate-100"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
