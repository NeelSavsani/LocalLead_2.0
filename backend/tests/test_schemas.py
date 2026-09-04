import pytest
from pydantic import ValidationError
from app.models.schemas import ScanRequest, LeadRecord, ScanProgress, ScanCandidateEvent


def test_scan_request_valid():
    req = ScanRequest(location="Gandhinagar, Gujarat", category="Auto Garage", limit=15)
    assert req.location == "Gandhinagar, Gujarat"
    assert req.category == "Auto Garage"
    assert req.limit == 15
    assert req.use_mock is False


def test_scan_request_limits():
    # Boundary validation: limit must be between 1 and 100
    with pytest.raises(ValidationError):
        ScanRequest(location="Test", category="Cafe", limit=0)

    with pytest.raises(ValidationError):
        ScanRequest(location="Test", category="Cafe", limit=101)


def test_lead_record_defaults():
    lead = LeadRecord(
        id="lead-1",
        name="Shree Ram Auto Care",
        category="Auto Garage",
        address="Sector 16, Gandhinagar",
    )
    assert lead.has_maps_site is False
    assert lead.has_web_site is False
    assert lead.verification_status == "No Standalone Website Found"
    assert lead.call_status == "Pending Call"
    assert "Gandhinagar" in lead.address


def test_scan_progress_state():
    progress = ScanProgress(
        job_id="job-123",
        processed_count=10,
        qualified_count=4,
        target_limit=10,
        current_business="Shree Maruti Spares",
    )
    assert progress.is_completed is False
    assert progress.qualified_count == 4
