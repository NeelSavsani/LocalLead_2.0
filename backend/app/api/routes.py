import asyncio
import json
import os
from typing import AsyncGenerator
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse

from app.config import settings
from app.models.schemas import (
    ScanProgress,
    ScanRequest,
    StartScanResponse,
)
from app.services.excel_exporter import generate_leads_excel
from app.services.scanner import scanner_service

router = APIRouter(prefix="/api/leads", tags=["Leads Pipeline"])


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


@router.get("/stream/{job_id}")
async def stream_scan_progress(job_id: str):
    """
    Server-Sent Events (SSE) endpoint streaming real-time candidate verification telemetry:
    - Layer 1 Google Maps check events
    - Layer 2 Organic search & directory exclusion checks
    - Instant qualified lead announcements
    - Completion signal when target limit is reached
    """
    job = scanner_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job '{job_id}' not found.",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        # If job has already completed before connection, yield current state and finish
        if job.is_completed:
            complete_data = {
                "event": "completed",
                "job_id": job.job_id,
                "status": "COMPLETED",
                "reason": f"Job already completed with {job.qualified_count} leads.",
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
                
                payload = {
                    "event": "candidate_evaluated",
                    "job_id": event.job_id,
                    "candidate_name": event.candidate_name,
                    "status": event.status,
                    "reason": event.reason,
                    "qualified_count": event.qualified_count,
                    "target_limit": event.target_limit,
                    "lead": event.lead.model_dump() if event.lead else None,
                }
                yield f"data: {json.dumps(payload)}\n\n"

                if event.status == "COMPLETED":
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
