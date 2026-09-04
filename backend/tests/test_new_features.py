import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ScanRequest, clean_business_name, is_commercial_business
from app.services.places_service import construct_maps_url, extract_indian_phone
from app.services.scanner import scanner_service, ScanJob

client = TestClient(app)


def test_clean_business_name_and_residential_filter():
    # 1. Emoji & icon stripping
    assert clean_business_name("☕ Cafe Mocha ★") == "Cafe Mocha"
    assert clean_business_name("Janata Garage \ue934") == "Janata Garage"
    assert clean_business_name("  - Top Repair Works | Ahmedabad -  ") == "Top Repair Works"

    # 2. Reject residential entities
    assert not is_commercial_business("Patel Villa")
    assert not is_commercial_business("Shree Krishna Society")
    assert not is_commercial_business("Gokul Apartment")
    assert not is_commercial_business("Bunglow No 4")
    assert not is_commercial_business("Sweet Home")
    assert not is_commercial_business("Shivam Residency")
    assert not is_commercial_business("Royal Flat")

    # 3. Allow legitimate commercial businesses
    assert is_commercial_business("Home Decor Hub")
    assert is_commercial_business("West Coast Pharmaceutical")
    assert is_commercial_business("Apollo Pharmacy")
    assert is_commercial_business("The Project Cafe")


def test_construct_maps_url_deep_links():
    # 1. Place ID deep link
    url_place = construct_maps_url("West Coast Pharma", place_id="ChIJlzFSy52dXjkRQUsVz96AHeA")
    assert url_place == "https://www.google.com/maps/place/?q=place_id:ChIJlzFSy52dXjkRQUsVz96AHeA"

    # 2. CID deep link
    url_cid = construct_maps_url("The Project Cafe", cid="13198889410145898462")
    assert url_cid == "https://maps.google.com/?cid=13198889410145898462"

    # 3. Never manufacture a generic search URL: it would open a result list,
    # not this business's place drawer.
    url_query = construct_maps_url(
        name="Janata Garage",
        address="Near Ring Road, Ambawadi",
        location="Ahmedabad, Gujarat",
    )
    assert url_query == ""


def test_extract_indian_phone():
    assert extract_indian_phone("+91 99090 05694") == "+91 99090 05694"
    assert extract_indian_phone("+919909005694") == "+919909005694"
    assert extract_indian_phone("Call us on 09909040932 now") == "09909040932"
    assert extract_indian_phone("Landline: 079-26167608") == "079-26167608"
    assert extract_indian_phone("No phone available") == "N/A"


def test_stop_scan_endpoint():
    # 1. Start a scan
    resp = client.post(
        "/api/leads/start",
        json={
            "location": "Ahmedabad, Gujarat",
            "categories": ["Cafe"],
            "limit": 10,
            "use_mock": True,
        }
    )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]

    # 2. Call stop scan
    stop_resp = client.post(f"/api/leads/stop/{job_id}")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "STOPPED"

    # 3. Verify job state
    job = scanner_service.get_job(job_id)
    assert job is not None
    assert job.is_cancelled is True

    # 4. Stopping non-existent job returns 404
    err_resp = client.post("/api/leads/stop/nonexistent_id")
    assert err_resp.status_code == 404
