export interface ScanRequest {
  location: string;
  categories: string[];
  limit: number;
  use_mock: boolean;
}

export const CALL_STATUS_OPTIONS = [
  "Pending",
  "Interested",
  "Not Interested",
  "Not Reachable",
  "Other",
] as const;

export interface LeadRecord {
  id: string;
  name: string;
  category: string;
  phone: string;
  address: string;
  area?: string;
  latitude?: number;
  longitude?: number;
  maps_url?: string;
  has_maps_site: boolean;
  has_web_site: boolean;
  verification_status: string;
  call_status: string;
  pitch_angle: string;
  date_identified: string;
}

export interface ScanCandidateEvent {
  event: string;
  job_id: string;
  candidate_name: string;
  category?: string;
  status: "EVALUATING" | "DISQUALIFIED_MAPS" | "DISQUALIFIED_SEARCH" | "QUALIFIED" | "COMPLETED" | "STOPPED";
  reason: string;
  qualified_count: number;
  target_limit: number;
  lead?: LeadRecord | null;
}

export interface StartScanResponse {
  job_id: string;
  message: string;
  target_limit: number;
  categories: string[];
}

export interface StopScanResponse {
  job_id: string;
  status: string;
  message: string;
  qualified_count: number;
}

export interface ScanResultsResponse {
  job_id: string;
  status: string;
  is_completed: boolean;
  location: string;
  categories: string[];
  target_limit: number;
  qualified_count: number;
  leads: LeadRecord[];
}

export interface SheetLeadRecord extends LeadRecord {
  notes?: string;
  updated_at?: string | null;
}

export interface AddToSheetResponse {
  added_count: number;
  skipped_duplicates: number;
  total_leads: number;
}

export interface SheetListResponse {
  leads: SheetLeadRecord[];
  total_leads: number;
  categories: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function startScan(req: ScanRequest): Promise<StartScanResponse> {
  const res = await fetch(`${API_BASE}/api/leads/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to start scan" }));
    throw new Error(err.detail || `Server error ${res.status}`);
  }

  return res.json();
}

export async function stopScan(jobId: string): Promise<StopScanResponse> {
  const res = await fetch(`${API_BASE}/api/leads/stop/${jobId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to stop scan" }));
    throw new Error(err.detail || `Server error ${res.status}`);
  }

  return res.json();
}

export async function getScanResults(jobId: string): Promise<ScanResultsResponse> {
  const res = await fetch(`${API_BASE}/api/leads/results/${jobId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch scan results: ${res.status}`);
  }
  return res.json();
}

export function getExcelDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/leads/download/${jobId}`;
}

export function createEventSourceStream(
  jobId: string,
  onEvent: (event: ScanCandidateEvent) => void,
  onError: (err: any) => void
): EventSource {
  const es = new EventSource(`${API_BASE}/api/leads/stream/${jobId}`);

  es.onmessage = (messageEvent) => {
    try {
      const parsed: ScanCandidateEvent = JSON.parse(messageEvent.data);
      onEvent(parsed);
    } catch (e) {
      console.warn("Could not parse SSE payload:", messageEvent.data);
    }
  };

  es.onerror = (err) => {
    onError(err);
  };

  return es;
}

async function readError(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({ detail: fallback }));
  if (typeof err.detail === "string") return err.detail;
  return fallback;
}

export async function addLeadsToSheet(leads: LeadRecord[]): Promise<AddToSheetResponse> {
  const res = await fetch(`${API_BASE}/api/sheet/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(leads),
  });
  if (!res.ok) {
    throw new Error(await readError(res, "Failed to add leads to sheet"));
  }
  return res.json();
}

export async function getSheetLeads(params?: {
  search?: string;
  category?: string;
  call_status?: string;
}): Promise<SheetListResponse> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.category && params.category !== "All") query.set("category", params.category);
  if (params?.call_status && params.call_status !== "All") query.set("call_status", params.call_status);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const res = await fetch(`${API_BASE}/api/sheet${suffix}`);
  if (!res.ok) {
    throw new Error(await readError(res, "Failed to load sheet"));
  }
  return res.json();
}

export async function updateSheetLead(
  leadId: string,
  payload: { call_status?: string; notes?: string }
): Promise<SheetLeadRecord> {
  const res = await fetch(`${API_BASE}/api/sheet/${encodeURIComponent(leadId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readError(res, "Failed to update lead"));
  }
  return res.json();
}

export async function deleteSheetLead(leadId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sheet/${encodeURIComponent(leadId)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(await readError(res, "Failed to delete lead"));
  }
}

export function getSheetExcelDownloadUrl(): string {
  return `${API_BASE}/api/sheet/export`;
}
