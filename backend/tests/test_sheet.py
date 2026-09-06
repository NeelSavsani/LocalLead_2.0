import os
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import SheetLeadRecord
from app.services.sheet_service import sheet_service

_TEST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "_test_sheets")


@pytest.fixture
def isolated_sheet():
    os.makedirs(_TEST_DIR, exist_ok=True)
    db_path = os.path.join(_TEST_DIR, f"sheet_{uuid.uuid4().hex}.db")
    original = sheet_service.db_path
    sheet_service.rebind(db_path)
    yield sheet_service
    sheet_service.rebind(original)
    try:
        os.remove(db_path)
    except OSError:
        pass


def _lead(**overrides) -> dict:
    base = {
        "id": "LLP-001",
        "name": "Maruti Motors & Car Care",
        "category": "Garage",
        "phone": "+91 98250 14820",
        "address": "Plot 12, GIDC Electronic Estate, Gandhinagar",
        "area": "Sector 25",
        "maps_url": "https://maps.google.com/?cid=111",
        "verification_status": "No Standalone Website Found",
        "call_status": "Pending Call",
    }
    base.update(overrides)
    return base


def test_sheet_lead_record_defaults_pending():
    record = SheetLeadRecord(
        id="SHT-0001",
        name="Cafe Mocha",
        category="Cafe",
        address="Ring Road, Surat",
        call_status="Pending Call",
    )
    assert record.call_status == "Pending"


def test_add_skips_duplicate_phone_and_preserves_existing(isolated_sheet):
    client = TestClient(app)

    first = client.post("/api/sheet/add", json=[_lead()])
    assert first.status_code == 200
    assert first.json() == {"added_count": 1, "skipped_duplicates": 0, "total_leads": 1}

    # Same phone, different maps URL and name — must skip and keep original
    dup_phone = client.post(
        "/api/sheet/add",
        json=[
            _lead(
                id="LLP-099",
                name="Other Garage Name",
                maps_url="https://maps.google.com/?cid=999",
                phone="9825014820",
            )
        ],
    )
    assert dup_phone.json()["added_count"] == 0
    assert dup_phone.json()["skipped_duplicates"] == 1
    assert dup_phone.json()["total_leads"] == 1

    listed = client.get("/api/sheet").json()["leads"]
    assert len(listed) == 1
    assert listed[0]["name"] == "Maruti Motors & Car Care"
    assert listed[0]["maps_url"] == "https://maps.google.com/?cid=111"
    assert listed[0]["call_status"] == "Pending"


def test_add_skips_duplicate_maps_url(isolated_sheet):
    client = TestClient(app)
    client.post("/api/sheet/add", json=[_lead(phone="N/A")])

    dup_maps = client.post(
        "/api/sheet/add",
        json=[
            _lead(
                id="LLP-002",
                name="Shree Ram Auto Care",
                phone="+91 90000 11111",
                maps_url="https://maps.google.com/?cid=111",
            )
        ],
    )
    body = dup_maps.json()
    assert body["added_count"] == 0
    assert body["skipped_duplicates"] == 1
    assert body["total_leads"] == 1


def test_add_unique_then_mixed_batch(isolated_sheet):
    client = TestClient(app)
    client.post("/api/sheet/add", json=[_lead()])

    batch = client.post(
        "/api/sheet/add",
        json=[
            _lead(),  # duplicate phone + maps
            _lead(
                id="LLP-002",
                name="The Project Cafe",
                category="Cafe",
                phone="+91 98765 43210",
                maps_url="https://maps.google.com/?cid=222",
                address="Adajan, Surat Gujarat",
            ),
        ],
    )
    body = batch.json()
    assert body["added_count"] == 1
    assert body["skipped_duplicates"] == 1
    assert body["total_leads"] == 2


def test_sheet_patch_delete_filter_and_export(isolated_sheet):
    client = TestClient(app)
    client.post(
        "/api/sheet/add",
        json=[
            _lead(),
            _lead(
                id="LLP-002",
                name="The Project Cafe",
                category="Cafe",
                phone="+91 98765 43210",
                maps_url="https://maps.google.com/?cid=222",
                address="Adajan, Surat Gujarat",
                area="Adajan",
            ),
        ],
    )

    listed = client.get("/api/sheet").json()
    cafe_id = next(item["id"] for item in listed["leads"] if item["category"] == "Cafe")

    patched = client.patch(f"/api/sheet/{cafe_id}", json={"call_status": "Interested", "notes": "Call back Monday"})
    assert patched.status_code == 200
    assert patched.json()["call_status"] == "Interested"
    assert patched.json()["notes"] == "Call back Monday"

    filtered = client.get("/api/sheet", params={"category": "Cafe", "call_status": "Interested"})
    assert len(filtered.json()["leads"]) == 1
    assert filtered.json()["total_leads"] == 2

    searched = client.get("/api/sheet", params={"search": "adajan"})
    assert len(searched.json()["leads"]) == 1

    export = client.get("/api/sheet/export")
    assert export.status_code == 200
    assert "spreadsheetml" in export.headers["content-type"]
    assert len(export.content) > 1000

    deleted = client.delete(f"/api/sheet/{cafe_id}")
    assert deleted.status_code == 200
    assert deleted.json()["total_leads"] == 1
    assert client.get("/api/sheet").json()["total_leads"] == 1
    assert client.patch("/api/sheet/SHT-9999", json={"call_status": "Other"}).status_code == 404
