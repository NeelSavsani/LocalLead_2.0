import os
import re
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

from app.models.schemas import LeadRecord, SheetLeadRecord, normalize_call_status

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_PATH = os.path.join(_BACKEND_ROOT, "data", "sheet_leads.db")

_PHONE_PLACEHOLDERS = {"", "n/a", "na", "none", "-", "null"}


def default_db_path() -> str:
    return os.environ.get("SHEET_DB_PATH") or DEFAULT_DB_PATH


def normalize_phone_key(phone: Optional[str]) -> Optional[str]:
    """Return a uniqueness key for a phone number, or None if unavailable."""
    if phone is None:
        return None
    raw = str(phone).strip()
    if raw.lower() in _PHONE_PLACEHOLDERS:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 6:
        return None
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def normalize_maps_key(maps_url: Optional[str]) -> Optional[str]:
    if not maps_url:
        return None
    cleaned = str(maps_url).strip().rstrip("/")
    return cleaned or None


class SheetService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or default_db_path()
        self._lock = threading.Lock()
        self._ensure_db()

    def rebind(self, db_path: str) -> None:
        with self._lock:
            self.db_path = db_path
            self._ensure_db()

    def _ensure_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sheet_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT,
                    phone TEXT,
                    address TEXT,
                    area TEXT,
                    latitude REAL,
                    longitude REAL,
                    maps_url TEXT,
                    has_maps_site INTEGER DEFAULT 0,
                    has_web_site INTEGER DEFAULT 0,
                    verification_status TEXT,
                    call_status TEXT DEFAULT 'Pending',
                    notes TEXT DEFAULT '',
                    date_identified TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _display_id(pk: int) -> str:
        return f"SHT-{int(pk):04d}"

    @staticmethod
    def _parse_id(lead_id: str) -> Optional[int]:
        if lead_id is None:
            return None
        raw = str(lead_id).strip()
        if not raw:
            return None
        if raw.upper().startswith("SHT-"):
            raw = raw.split("-", 1)[1]
        try:
            return int(raw)
        except ValueError:
            return None

    def _row_to_record(self, row: sqlite3.Row) -> SheetLeadRecord:
        return SheetLeadRecord(
            id=self._display_id(row["id"]),
            name=row["name"],
            category=row["category"] or "",
            phone=row["phone"] or "N/A",
            address=row["address"] or "",
            area=row["area"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            maps_url=row["maps_url"],
            has_maps_site=bool(row["has_maps_site"]),
            has_web_site=bool(row["has_web_site"]),
            verification_status=row["verification_status"] or "No Standalone Website Found",
            call_status=normalize_call_status(row["call_status"]),
            notes=row["notes"] or "",
            date_identified=row["date_identified"] or "",
            updated_at=row["updated_at"],
        )

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM sheet_leads").fetchone()[0])

    def list_leads(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        call_status: Optional[str] = None,
    ) -> List[SheetLeadRecord]:
        sql = "SELECT * FROM sheet_leads WHERE 1=1"
        params: List[object] = []

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            sql += """
                AND (
                    LOWER(name) LIKE ?
                    OR LOWER(IFNULL(phone, '')) LIKE ?
                    OR LOWER(IFNULL(address, '')) LIKE ?
                    OR LOWER(IFNULL(area, '')) LIKE ?
                )
            """
            params.extend([term, term, term, term])

        if category and category.strip() and category.strip().lower() != "all":
            sql += " AND LOWER(category) = ?"
            params.append(category.strip().lower())

        if call_status and call_status.strip() and call_status.strip().lower() != "all":
            sql += " AND LOWER(call_status) = ?"
            params.append(normalize_call_status(call_status).lower())

        sql += " ORDER BY id ASC"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_record(row) for row in rows]

    def categories(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM sheet_leads WHERE category IS NOT NULL AND TRIM(category) != '' ORDER BY category COLLATE NOCASE"
            ).fetchall()
            return [row["category"] for row in rows]

    def add_leads(self, leads: Sequence[LeadRecord]) -> Tuple[int, int, int]:
        """Insert unique leads. Duplicate if phone (when available) OR exact maps_url already exists."""
        added = 0
        skipped = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        with self._lock:
            with self._connect() as conn:
                existing_phones, existing_maps = self._load_keys(conn)

                for lead in leads:
                    phone_key = normalize_phone_key(lead.phone)
                    maps_key = normalize_maps_key(lead.maps_url)

                    is_duplicate = False
                    if phone_key and phone_key in existing_phones:
                        is_duplicate = True
                    if maps_key and maps_key in existing_maps:
                        is_duplicate = True

                    if is_duplicate:
                        skipped += 1
                        continue

                    conn.execute(
                        """
                        INSERT INTO sheet_leads (
                            name, category, phone, address, area,
                            latitude, longitude, maps_url,
                            has_maps_site, has_web_site,
                            verification_status, call_status, notes,
                            date_identified, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            lead.name,
                            lead.category,
                            lead.phone,
                            lead.address,
                            lead.area,
                            lead.latitude,
                            lead.longitude,
                            lead.maps_url,
                            1 if lead.has_maps_site else 0,
                            1 if lead.has_web_site else 0,
                            lead.verification_status or "No Standalone Website Found",
                            normalize_call_status(lead.call_status),
                            "",
                            lead.date_identified or now,
                            now,
                        ),
                    )
                    added += 1
                    if phone_key:
                        existing_phones.add(phone_key)
                    if maps_key:
                        existing_maps.add(maps_key)

                conn.commit()
                total = int(conn.execute("SELECT COUNT(*) FROM sheet_leads").fetchone()[0])

        return added, skipped, total

    def _load_keys(self, conn: sqlite3.Connection) -> Tuple[set, set]:
        phones = set()
        maps = set()
        for row in conn.execute("SELECT phone, maps_url FROM sheet_leads"):
            phone_key = normalize_phone_key(row["phone"])
            maps_key = normalize_maps_key(row["maps_url"])
            if phone_key:
                phones.add(phone_key)
            if maps_key:
                maps.add(maps_key)
        return phones, maps

    def update_lead(self, lead_id: str, call_status: Optional[str] = None, notes: Optional[str] = None) -> Optional[SheetLeadRecord]:
        pk = self._parse_id(lead_id)
        if pk is None:
            return None

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        fields = []
        params: List[object] = []

        if call_status is not None:
            fields.append("call_status = ?")
            params.append(normalize_call_status(call_status))
        if notes is not None:
            fields.append("notes = ?")
            params.append(notes)

        if not fields:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM sheet_leads WHERE id = ?", (pk,)).fetchone()
                return self._row_to_record(row) if row else None

        fields.append("updated_at = ?")
        params.append(now)
        params.append(pk)

        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    f"UPDATE sheet_leads SET {', '.join(fields)} WHERE id = ?",
                    params,
                )
                if cur.rowcount == 0:
                    return None
                conn.commit()
                row = conn.execute("SELECT * FROM sheet_leads WHERE id = ?", (pk,)).fetchone()
                return self._row_to_record(row) if row else None

    def delete_lead(self, lead_id: str) -> bool:
        pk = self._parse_id(lead_id)
        if pk is None:
            return False
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM sheet_leads WHERE id = ?", (pk,))
                conn.commit()
                return cur.rowcount > 0

    def get_lead(self, lead_id: str) -> Optional[SheetLeadRecord]:
        pk = self._parse_id(lead_id)
        if pk is None:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sheet_leads WHERE id = ?", (pk,)).fetchone()
            return self._row_to_record(row) if row else None


sheet_service = SheetService()
