import pytest
from app.models.schemas import ScanRequest
from app.services.search_verifier import (
    EXCLUDED_DOMAINS,
    is_blacklisted_domain,
    normalize_domain,
    verify_independent_website,
)
from app.services import places_service
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


@pytest.mark.asyncio
async def test_places_service_candidates_extraction():
    candidates = await fetch_places_candidates(
        location="Surat, Gujarat",
        categories=["Cafe", "Auto Garage"],
        limit=10,
        use_mock=True,
    )
    assert len(candidates) >= 5
    # Candidates always have drawer-backed phones and direct place links.
    for c in candidates:
        assert "cid=" in c["maps_url"] or "place_id:" in c["maps_url"] or "/maps/place/" in c["maps_url"]
        assert c["phone"] != "N/A"
        assert "Surat" in c["address"] or "Surat" in c["maps_url"]
        assert c["category"] in ["Cafe", "Auto Garage"]


@pytest.mark.asyncio
async def test_gmaps_browser_uses_http_fallback_when_playwright_is_unavailable(monkeypatch):
    async def fallback(location, category, max_items):
        return [{"name": "Fallback Cafe", "category": category}]

    monkeypatch.setattr(places_service, "HAS_PLAYWRIGHT", False)
    monkeypatch.setattr(places_service, "_http_local_cards_fallback", fallback)

    assert await places_service.fetch_from_gmaps_browser("Surat, Gujarat", "Cafe", 1) == [
        {"name": "Fallback Cafe", "category": "Cafe"}
    ]


@pytest.mark.asyncio
async def test_scanner_strict_limit_enforcement_3():
    scanner = ScannerService()
    req = ScanRequest(
        location="Surat, Gujarat",
        categories=["Cafe", "Auto Garage"],
        limit=3,
        use_mock=True,
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
        assert "cid=" in lead.maps_url or "place_id:" in lead.maps_url or "/maps/place/" in lead.maps_url
        assert lead.phone != "N/A"


@pytest.mark.asyncio
async def test_scanner_strict_limit_enforcement_multi_category():
    scanner = ScannerService()
    req = ScanRequest(
        location="Surat, Gujarat",
        categories=["Cafe", "Garage"],
        limit=5,
        use_mock=True,
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


def test_listicle_rejection():
    from app.services.places_service import is_listicle_title
    from app.models.schemas import is_commercial_business

    listicles = [
        "Top 10 Cafes in Junagadh",
        "The Best Cafes in Junagadh",
        "Best Coffee Shops in Junagadh",
        "List of Cafes in Gujarat",
        "Top Coffee Shops in Junagadh",
        "Garages in Ahmedabad",
        "Restaurants in Surat",
        "Cafes near me",
        "10 best restaurants in town",
    ]
    for title in listicles:
        assert is_listicle_title(title) is True
        assert is_commercial_business(title) is False

    real_businesses = [
        "Gigil Cafe",
        "Hideout Cafe & Food",
        "AROMA CAFE",
        "Tea Post",
        "One Step Up Cafe",
        "Signature Restro & Cafe",
        "Maruti Car Care",
    ]
    for name in real_businesses:
        assert is_listicle_title(name) is False
        assert is_commercial_business(name) is True


def test_indian_phone_extraction():
    from app.services.places_service import extract_indian_phone

    assert extract_indian_phone("Phone: 085305 26269") in ["085305 26269", "08530526269"]
    assert extract_indian_phone("+91 98765 43210") in ["+91 98765 43210", "+919876543210"]
    assert extract_indian_phone("Call us at 06352092843 now") == "06352092843"
    assert extract_indian_phone("0285-2621234") == "0285-2621234"
    assert extract_indian_phone("No contact number available") == "N/A"
    assert extract_indian_phone(None) == "N/A"


def test_construct_direct_maps_url():
    from app.services.places_service import construct_maps_url

    direct = "https://www.google.com/maps/place/Hideout+Cafe+%26+Food/@21.513343,70.461691,17z/data=!3m1!4b1"
    assert construct_maps_url("Hideout Cafe & Food", direct_url=direct) == direct

    cid_url = construct_maps_url("Hideout Cafe & Food", cid="1312367468165039661")
    assert cid_url == "https://maps.google.com/?cid=1312367468165039661"
