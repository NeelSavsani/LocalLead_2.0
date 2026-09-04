export interface ScanRequest {
  location: string;
  categories: string[];
  limit: number;
  use_mock: boolean;
}

export interface LeadRecord {
  id: string;
  name: string;
  category: string;
  phone: string;
  address: string;
  area?: string;
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
