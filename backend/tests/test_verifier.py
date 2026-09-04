import pytest
from app.models.schemas import ScanRequest
from app.services.search_verifier import (
    EXCLUDED_DOMAINS,
    is_blacklisted_domain,
    normalize_domain,
    verify_independent_website,
)
from app.services.places_service import fetch_places_candidates
from app.services.scanner import ScannerService


def test_normalize_domain():
    assert normalize_domain("https://www.justdial.com/Gandhinagar/Shop") == "justdial.com"
    assert normalize_domain("http://facebook.com/profile") == "facebook.com"
    assert normalize_domain("https://shreeramgarage.in/about") == "shreeramgarage.in"
    assert normalize_domain("www.indiamart.com:8080/company") == "indiamart.com"


def test_aggregator_blacklist_detection():
    # Directory & aggregator domains must be blacklisted
    assert is_blacklisted_domain("https://www.justdial.com/Gandhinagar/Cafe") is True
    assert is_blacklisted_domain("https://www.indiamart.com/company") is True
    assert is_blacklisted_domain("https://m.facebook.com/store") is True
    assert is_blacklisted_domain("https://www.instagram.com/p/123") is True
    assert is_blacklisted_domain("https://www.zomato.com/gandhinagar/cafe") is True
    assert is_blacklisted_domain("https://swiggy.com/restaurants/food") is True
    assert is_blacklisted_domain("https://sulekha.com/repair") is True
    assert is_blacklisted_domain("https://www.tradeindia.com/products") is True

    # Standalone private business websites must NOT be blacklisted
    assert is_blacklisted_domain("https://www.maruticarcare.in") is False
    assert is_blacklisted_domain("https://radhikadental.org") is False
    assert is_blacklisted_domain("https://karnavatibakers.com") is False


def test_search_verifier_with_directory_only_links():
    # Only directory/social listings -> Business has NO standalone website (QUALIFIED)
    mock_links = [
        "https://www.justdial.com/Gandhinagar/Maruti-Car-Care",
        "https://www.facebook.com/maruticarcare",
        "https://www.indiamart.com/maruti-care",
    ]
    result = verify_independent_website(
        business_name="Maruti Car Care",
        location="Gandhinagar, Gujarat",
        mock_urls=mock_links,
    )
    assert result["has_standalone_website"] is False
    assert len(result["standalone_urls"]) == 0


def test_search_verifier_with_standalone_website_detected():
    # Organic search result includes an independent domain -> Business owns a website (DISQUALIFIED)
    mock_links = [
        "https://www.justdial.com/Gandhinagar/Patel-Auto-Spares",
        "https://www.patelautospares.in",  # Standalone domain
        "https://www.indiamart.com/patel-spares",
    ]
    result = verify_independent_website(
        business_name="Patel Auto Spares",
        location="Gandhinagar, Gujarat",
        mock_urls=mock_links,
    )
    assert result["has_standalone_website"] is True
    assert "https://www.patelautospares.in" in result["standalone_urls"]


def test_places_service_candidates_extraction():
    candidates = fetch_places_candidates(
        location="Surat, Gujarat",
        categories=["Cafe", "Auto Garage"],
        limit=10,
    )
    assert len(candidates) >= 5
    # Must contain candidates with real addresses and maps_url containing place query
    for c in candidates:
        assert "google.com/maps" in c["maps_url"]
        assert "Surat" in c["address"] or "Surat" in c["maps_url"]
        assert c["category"] in ["Cafe", "Auto Garage"]


@pytest.mark.asyncio
async def test_scanner_strict_limit_enforcement_3():
    scanner = ScannerService()
    req = ScanRequest(
        location="Surat, Gujarat",
        categories=["Cafe", "Auto Garage"],
        limit=3,
    )
    job = scanner.create_job(req)
    # Run scanner with zero artificial sleep delay for fast test execution
    await scanner.run_scan(job, delay_seconds=0.0)

    assert job.status == "COMPLETED"
    assert job.is_completed is True
    # Strictly capped at 3 qualified leads!
    assert job.qualified_count == 3
    assert len(job.qualified_leads) == 3

    # Verify all 3 qualified leads have no website on Maps or Search
    for lead in job.qualified_leads:
        assert lead.has_maps_site is False
        assert lead.has_web_site is False
        assert lead.verification_status == "No Standalone Website Found"
        assert "https://www.google.com/maps/search/?api=1&query=" in lead.maps_url


@pytest.mark.asyncio
async def test_scanner_strict_limit_enforcement_multi_category():
    scanner = ScannerService()
    req = ScanRequest(
        location="Surat, Gujarat",
        categories=["Cafe", "Garage"],
        limit=5,
    )
    job = scanner.create_job(req)
    await scanner.run_scan(job, delay_seconds=0.0)

    assert job.status == "COMPLETED"
    assert job.is_completed is True
    assert job.qualified_count == 5
    assert len(job.qualified_leads) == 5
    # Verify categories are represented
    found_categories = {l.category for l in job.qualified_leads}
    assert len(found_categories) >= 1
