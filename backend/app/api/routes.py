import asyncio
import json
import os
from typing import AsyncGenerator, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse

from app.config import settings
from app.models.schemas import (
    AddToSheetResponse,
    LeadRecord,
    ScanProgress,
    ScanRequest,
    SheetListResponse,
    SheetUpdateRequest,
    StartScanResponse,
)
from app.services.excel_exporter import generate_leads_excel
from app.services.scanner import scanner_service
from app.services.sheet_service import sheet_service

router = APIRouter(prefix="/api/leads", tags=["Leads Pipeline"])
sheet_router = APIRouter(prefix="/api/sheet", tags=["Sheet Workspace"])


@router.post("/start", response_model=StartScanResponse, status_code=status.HTTP_201_CREATED)
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """
    Initiates a new background lead generation and dual-layer verification scan.
    Returns a unique job_id to subscribe to SSE streams and retrieve results.
    """
    job = scanner_service.create_job(request)

    # Launch scanning loop asynchronously in the background
    background_tasks.add_task(scanner_service.run_scan, job)

    return StartScanResponse(
        job_id=job.job_id,
        message="Scan initiated successfully. Connect to SSE stream for live updates.",
        target_limit=request.limit,
        categories=job.request.categories,
    )


@router.post("/stop/{job_id}")
async def stop_scan(job_id: str):
    """
    Halts an in-progress scan, sets job.is_cancelled = True,
    and preserves all qualified leads collected up to that point.
    """
    job = scanner_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job '{job_id}' not found.",
        )
    job.is_cancelled = True
    return {
        "job_id": job.job_id,
        "status": "STOPPED",
        "message": "Scan cancellation requested.",
        "qualified_count": job.qualified_count,
    }


@router.get("/stream/{job_id}")
async def stream_scan_progress(job_id: str):
    """
    Server-Sent Events (SSE) endpoint streaming real-time candidate verification telemetry:
    - Layer 1 Google Maps check events
    - Layer 2 Organic search & directory exclusion checks
    - Instant qualified lead announcements
    - Stop and completion signals
    """
    job = scanner_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job '{job_id}' not found.",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        # If job has already completed or stopped before connection, yield current state and finish
        if job.is_completed:
            evt_type = "scan_stopped" if job.status == "STOPPED" else "completed"
            complete_data = {
                "event": evt_type,
                "job_id": job.job_id,
                "status": job.status,
                "reason": f"Job {job.status.lower()} with {job.qualified_count} leads.",
                "qualified_count": job.qualified_count,
                "target_limit": job.request.limit,
            }
            yield f"data: {json.dumps(complete_data)}\n\n"
            return

        while True:
            try:
                # Wait for next event with a timeout to send keep-alive pings
                event = await asyncio.wait_for(job.events_queue.get(), timeout=15.0)
                if event is None:
                    # Sentinel signifying scan termination
                    break

                event_type = "scan_stopped" if event.status == "STOPPED" else "candidate_evaluated"
                payload = {
                    "event": event_type,
                    "job_id": event.job_id,
                    "candidate_name": event.candidate_name,
                    "status": event.status,
                    "reason": event.reason,
                    "qualified_count": event.qualified_count,
                    "target_limit": event.target_limit,
                    "lead": event.lead.model_dump() if event.lead else None,
                }
                yield f"data: {json.dumps(payload)}\n\n"

                if event.status in ["COMPLETED", "STOPPED"]:
                    break
            except asyncio.TimeoutError:
                # Keep-alive heartbeat ping
                yield ": keep-alive\n\n"
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status/{job_id}", response_model=ScanProgress)
async def get_scan_status(job_id: str):
    """
    Fetches the current progress and status of a scan job.
    """
    job = scanner_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job '{job_id}' not found.",
        )
    return job.to_progress()


@router.get("/results/{job_id}")
async def get_scan_results(job_id: str):
    """
    Fetches the final array of verified qualified leads for a job.
    """
    job = scanner_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job '{job_id}' not found.",
        )

    return {
        "job_id": job.job_id,
        "status": job.status,
        "is_completed": job.is_completed,
        "location": job.request.location,
        "categories": job.request.categories,
        "target_limit": job.request.limit,
        "qualified_count": job.qualified_count,
        "leads": [lead.model_dump() for lead in job.qualified_leads],
    }


@router.get("/download/{job_id}")
async def download_excel(job_id: str):
    """
    Downloads the professionally styled .xlsx workbook pre-populated
    with qualified leads and CRM data validation dropdowns.
    """
    job = scanner_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job '{job_id}' not found.",
        )

    # If excel path hasn't been generated yet (e.g. download requested mid-scan)
    file_path = job.excel_path
    if not file_path or not os.path.exists(file_path):
        file_path = generate_leads_excel(
            job_id=job.job_id,
            location=job.request.location,
            leads=job.qualified_leads,
        )
        job.excel_path = file_path

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to locate generated Excel workbook.",
        )

    cat_slug = "_".join(c.replace(" ", "_") for c in job.request.categories) or "Leads"
    filename = f"LocalLeadPulse_{cat_slug}_{job.job_id}.xlsx"

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@sheet_router.post("/add", response_model=AddToSheetResponse)
async def add_leads_to_sheet(leads: List[LeadRecord]):
    """
    Persist unique scanner leads. A record is skipped when its phone
    (if present) or exact maps_url already exists in the sheet store.
    Existing rows are never overwritten.
    """
    added, skipped, total = sheet_service.add_leads(leads)
    return AddToSheetResponse(
        added_count=added,
        skipped_duplicates=skipped,
        total_leads=total,
    )


@sheet_router.get("/export")
async def export_sheet_excel():
    """Download the consolidated sheet workbook with current CRM formatting."""
    leads = sheet_service.list_leads()
    file_path = generate_leads_excel(
        job_id="sheet-workspace",
        location="Sheet Workspace",
        leads=leads,
    )
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="LocalLeadPulse_Sheet_Workspace.xlsx",
    )


@sheet_router.get("", response_model=SheetListResponse)
@sheet_router.get("/", response_model=SheetListResponse)
async def list_sheet_leads(
    search: Optional[str] = Query(default=None, description="Filter by name, phone, address, or landmark"),
    category: Optional[str] = Query(default=None),
    call_status: Optional[str] = Query(default=None),
):
    leads = sheet_service.list_leads(search=search, category=category, call_status=call_status)
    return SheetListResponse(
        leads=leads,
        total_leads=sheet_service.count(),
        categories=sheet_service.categories(),
    )


@sheet_router.patch("/{lead_id}")
async def update_sheet_lead(lead_id: str, payload: SheetUpdateRequest):
    updated = sheet_service.update_lead(
        lead_id,
        call_status=payload.call_status,
        notes=payload.notes,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sheet lead '{lead_id}' not found.",
        )
    return updated


@sheet_router.delete("/{lead_id}")
async def delete_sheet_lead(lead_id: str):
    deleted = sheet_service.delete_lead(lead_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sheet lead '{lead_id}' not found.",
        )
    return {"deleted": True, "lead_id": lead_id, "total_leads": sheet_service.count()}
