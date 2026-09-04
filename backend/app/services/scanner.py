import asyncio
import uuid
import urllib.parse
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional

from app.config import settings
from app.models.schemas import (
    LeadRecord,
    ScanCandidateEvent,
    ScanProgress,
    ScanRequest,
)
from app.services.places_service import fetch_places_candidates, construct_maps_url, is_direct_place_url, extract_indian_phone
from app.services.search_verifier import verify_independent_website
from app.services.excel_exporter import generate_leads_excel


class ScanJob:
    def __init__(self, request: ScanRequest, job_id: Optional[str] = None):
        self.job_id = job_id or str(uuid.uuid4())[:8]
        self.request = request
        self.status: str = "PENDING"
        self.processed_count: int = 0
        self.qualified_leads: List[LeadRecord] = []
        self.events_queue: asyncio.Queue = asyncio.Queue()
        self.is_completed: bool = False
        self.is_cancelled: bool = False
        self.created_at: str = datetime.now().isoformat()
        self.excel_path: Optional[str] = None

    @property
    def qualified_count(self) -> int:
        return len(self.qualified_leads)

    def to_progress(self, current_business: Optional[str] = None, latest_log: Optional[str] = None) -> ScanProgress:
        return ScanProgress(
            job_id=self.job_id,
            processed_count=self.processed_count,
            qualified_count=self.qualified_count,
            target_limit=self.request.limit,
            current_business=current_business,
            status=self.status,
            latest_log=latest_log,
            is_completed=self.is_completed,
        )


class ScannerService:
    def __init__(self):
        self.jobs: Dict[str, ScanJob] = {}

    def get_job(self, job_id: str) -> Optional[ScanJob]:
        return self.jobs.get(job_id)

    def create_job(self, request: ScanRequest) -> ScanJob:
        job = ScanJob(request=request)
        self.jobs[job.job_id] = job
        return job

    def stop_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if job:
            job.is_cancelled = True
            return True
        return False

    async def run_scan(self, job: ScanJob, delay_seconds: float = 0.05) -> None:
        """
        Orchestration loop:
        1. Queries candidate businesses from Google Places / local dataset.
        2. Evaluates each candidate through Layer 1 (Google Maps) and Layer 2 (Search Aggregators).
        3. Strictly halts the moment qualified_count reaches request.limit or job.is_cancelled is True.
        """
        job.status = "RUNNING"
        limit = job.request.limit
        location = job.request.location
        categories = job.request.categories or ["Local Business"]
        use_mock = job.request.use_mock or settings.MOCK_MODE
        cat_label = ", ".join(categories)

        # Emit initial job start event
        await job.events_queue.put(
            ScanCandidateEvent(
                job_id=job.job_id,
                candidate_name="System",
                status="EVALUATING",
                reason=f"Initializing scan for categories [{cat_label}] in '{location}' with target limit {limit}...",
                qualified_count=0,
                target_limit=limit,
            )
        )

        candidates = await fetch_places_candidates(
            location=location,
            categories=categories,
            limit=limit,
            use_mock=use_mock,
            api_key=settings.GOOGLE_MAPS_API_KEY,
        )

        for candidate in candidates:
            # STOP SCAN CHECK
            if job.is_cancelled:
                await job.events_queue.put(
                    ScanCandidateEvent(
                        job_id=job.job_id,
                        candidate_name="System",
                        status="STOPPED",
                        reason=f"Scan stopped by user. Preserving {job.qualified_count} verified leads.",
                        qualified_count=job.qualified_count,
                        target_limit=limit,
                    )
                )
                break

            # STRICT LIMIT ENFORCEMENT
            if job.qualified_count >= limit:
                break

            name = candidate.get("name", "Unknown Shop")
            maps_website = candidate.get("maps_website")
            mock_links = candidate.get("search_links")

            # A sales lead must be both callable and link to one specific place
            # drawer.  Do this before web verification to avoid wasting searches.
            phone = extract_indian_phone(candidate.get("phone"))
            maps_url = candidate.get("maps_url") or construct_maps_url(
                name=name,
                place_id=candidate.get("place_id"),
                cid=candidate.get("cid"),
            )
            if not is_direct_place_url(maps_url) or (job.request.require_phone and phone == "N/A"):
                job.processed_count += 1
                reason = "No direct Google Maps place link" if not is_direct_place_url(maps_url) else "No callable phone number in Google Maps place drawer"
                await job.events_queue.put(ScanCandidateEvent(
                    job_id=job.job_id, candidate_name=name, status="DISQUALIFIED_CONTACT",
                    reason=reason, qualified_count=job.qualified_count, target_limit=limit,
                ))
                continue

            # Telemetry update
            await job.events_queue.put(
                ScanCandidateEvent(
                    job_id=job.job_id,
                    candidate_name=name,
                    status="EVALUATING",
                    reason=f"Checking Google Maps profile for '{name}'...",
                    qualified_count=job.qualified_count,
                    target_limit=limit,
                )
            )
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

            # --- LAYER 1 VERIFICATION: Google Maps Website Check ---
            # If Google Maps listing has an active Website button or link away from Google, disqualify immediately
            if maps_website:
                job.processed_count += 1
                await job.events_queue.put(
                    ScanCandidateEvent(
                        job_id=job.job_id,
                        candidate_name=name,
                        status="DISQUALIFIED_MAPS",
                        reason=f"Listing has website attached on Google Maps ({maps_website})",
                        qualified_count=job.qualified_count,
                        target_limit=limit,
                    )
                )
                continue  # Disqualified, move to next

            # --- LAYER 2 VERIFICATION: Organic Search & Aggregator Blacklist ---
            await job.events_queue.put(
                ScanCandidateEvent(
                    job_id=job.job_id,
                    candidate_name=name,
                    status="EVALUATING",
                    reason=f"No site on Maps. Querying search engines excluding aggregators for '{name}'...",
                    qualified_count=job.qualified_count,
                    target_limit=limit,
                )
            )

            # Perform Layer 2 check
            verifier_result = verify_independent_website(
                business_name=name,
                location=location,
                mock_urls=mock_links,
                api_key=settings.GOOGLE_SEARCH_API_KEY,
                search_engine_id=settings.GOOGLE_SEARCH_ENGINE_ID,
            )

            job.processed_count += 1

            if verifier_result["has_standalone_website"]:
                # False negative on Maps, business actually owns an official website
                detected_site = verifier_result["standalone_urls"][0]
                await job.events_queue.put(
                    ScanCandidateEvent(
                        job_id=job.job_id,
                        candidate_name=name,
                        status="DISQUALIFIED_SEARCH",
                        reason=f"Found standalone business website on search: {detected_site}",
                        qualified_count=job.qualified_count,
                        target_limit=limit,
                    )
                )
                continue

            # --- QUALIFIED LEAD: Passed both layers! ---
            cand_category = candidate.get("category") or categories[0]
            lead_id = f"LLP-{len(job.qualified_leads) + 1:03d}"
            try:
                lead = LeadRecord(
                    id=lead_id,
                    name=name,
                    category=cand_category,
                    phone=phone,
                    address=candidate.get("address", location),
                    area=candidate.get("area", location.split(",")[0].strip()),
                    maps_url=maps_url,
                    has_maps_site=False,
                    has_web_site=False,
                    verification_status="No Standalone Website Found",
                    call_status="Pending Call",
                    pitch_angle=candidate.get("pitch_angle", f"Direct website & online ordering portal for {cand_category}"),
                )
            except Exception:
                # Discard invalid/residential entities rejected by validator
                continue

            job.qualified_leads.append(lead)

            await job.events_queue.put(
                ScanCandidateEvent(
                    job_id=job.job_id,
                    candidate_name=name,
                    status="QUALIFIED",
                    reason=f"Verified website-less lead! ({job.qualified_count}/{limit})",
                    qualified_count=job.qualified_count,
                    target_limit=limit,
                    lead=lead,
                )
            )

            # Check again after incrementing
            if job.qualified_count >= limit or job.is_cancelled:
                break

        # Finalize job status and generate styled Excel workbook preserving leads
        if job.is_cancelled:
            job.status = "STOPPED"
        else:
            job.status = "COMPLETED"
        job.is_completed = True

        try:
            job.excel_path = generate_leads_excel(
                job_id=job.job_id,
                location=location,
                leads=job.qualified_leads,
            )
        except Exception:
            job.excel_path = None

        # Signal completion or stop to SSE consumers
        if not job.is_cancelled:
            await job.events_queue.put(
                ScanCandidateEvent(
                    job_id=job.job_id,
                    candidate_name="System",
                    status="COMPLETED",
                    reason=f"Scan completed! Collected {job.qualified_count} verified leads matching limit {limit}.",
                    qualified_count=job.qualified_count,
                    target_limit=limit,
                )
            )
        await job.events_queue.put(None)  # Sentinel for generator exhaustion


# Global singleton scanner service instance
scanner_service = ScannerService()
