import re
import urllib.parse
from typing import Dict, List, Optional, Set
import requests

from app.config import settings
from app.models.schemas import clean_business_name, is_commercial_business

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False


CATEGORY_SYNONYMS: Dict[str, List[str]] = {
    "garage": ["car repair", "auto repair", "car service", "mechanic", "automobile workshop"],
    "auto garage": ["car repair", "car service", "auto repair", "mechanic", "garage"],
    "cafe": ["cafe", "coffee shop", "bakery", "tea"],
    "restaurant": ["restaurant", "dining", "dhaba", "food"],
    "clinic": ["dental clinic", "clinic", "hospital", "dentist", "doctor"],
    "dentist": ["dental clinic", "dentist", "dental care"],
    "pharmacy": ["medical store", "chemist", "pharmacy", "medicine"],
    "hardware": ["hardware store", "plywood", "electricals", "sanitary"],
    "hardware store": ["hardware store", "plywood", "electrical store"],
    "boutique": ["boutique", "designer dress", "clothing store"],
    "salon": ["beauty salon", "hair salon", "family salon", "spa"],
}

CATEGORY_PITCH_ANGLES: Dict[str, str] = {
    "auto garage": "Online breakdown assistance and WhatsApp service slot booking",
    "garage": "Online service slot reservation & breakdown assistance request portal",
    "cafe": "Direct QR table ordering & save 25-30% food aggregator commissions",
    "restaurant": "Direct digital menu & table pre-booking without heavy platform commissions",
    "clinic": "Automated patient consult booking & zero-wait appointment queue",
    "dentist": "Instant online doctor consult booking & timing slot scheduler",
    "pharmacy": "Direct digital catalog, recurring prescription refill & home delivery portal",
    "hardware": "Interactive digital product showcase with direct WhatsApp quotation",
    "hardware store": "Digital sanitaryware & architectural hardware showcase catalog",
    "boutique": "Bridal wear portfolio gallery & custom tailoring booking page",
    "salon": "Online chair booking & wedding bridal package pricing calculator",
}

# Accurate Indian Phone Number Pattern per specification:
# (?:(?:\+91|0)?[6-9]\d{9}|0\d{2,4}[-\s]?\d{6,8})
INDIAN_PHONE_REGEX = re.compile(
    r'(?:(?:\+91[\s-]?)?[6-9]\d{9}|(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}|0\d{2,4}[-\s]?\d{6,8})'
)


def get_pitch_angle(category: str) -> str:
    cat_lower = category.lower()
    for key, pitch in CATEGORY_PITCH_ANGLES.items():
        if key in cat_lower or cat_lower in key:
            return pitch
    return f"Digital storefront & direct customer booking portal for {category}"


def extract_indian_phone(text: Optional[str]) -> str:
    r"""
    Extracts Indian phone numbers from text using standard regex:
    (?:(?:\+91|0)?[6-9]\d{9}|0\d{2,4}[-\s]?\d{6,8})
    """
    if not text:
        return "N/A"
    matches = INDIAN_PHONE_REGEX.findall(str(text))
    for m in matches:
        clean = re.sub(r'[\s-]', '', m)
        if clean.startswith(('00', '19', '20')):
            continue
        if len(clean) in [10, 11, 12, 13]:
            return m.strip()
    return "N/A"


def construct_maps_url(
    name: str,
    address: Optional[str] = None,
    location: Optional[str] = None,
    place_id: Optional[str] = None,
    cid: Optional[str] = None,
) -> str:
    """
    Constructs an exact direct Google Maps deep-link per specification:
    - If place_id is captured: https://www.google.com/maps/place/?q=place_id:{place_id}
    - If CID is captured: https://maps.google.com/?cid={cid}
    - Exact query: https://www.google.com/maps/search/?api=1&query={encoded_name}+{encoded_address}+{encoded_location}
    """
    if place_id and len(place_id.strip()) > 5:
        return f"https://www.google.com/maps/place/?q=place_id:{urllib.parse.quote_plus(place_id.strip())}"
    if cid and len(cid.strip()) > 3:
        return f"https://maps.google.com/?cid={urllib.parse.quote_plus(cid.strip())}"

    encoded_name = urllib.parse.quote_plus(name.strip())

    clean_addr = ""
    if address:
        addr_str = address.strip()
        if addr_str.lower().startswith(name.strip().lower()):
            addr_str = addr_str[len(name.strip()):].lstrip(", -")
        if location and addr_str.lower().endswith(location.strip().lower()):
            addr_str = addr_str[:-len(location.strip())].rstrip(", -")
        clean_addr = addr_str.strip()

    encoded_address = urllib.parse.quote_plus(clean_addr) if clean_addr else ""
    encoded_location = urllib.parse.quote_plus(location.strip()) if location else ""

    parts = [p for p in [encoded_name, encoded_address, encoded_location] if p]
    query_str = "+".join(parts)
    return f"https://www.google.com/maps/search/?api=1&query={query_str}"


def is_valid_commercial_address(
    display_name: str,
    osm_class: Optional[str] = None,
    osm_type: Optional[str] = None,
    addr_details: Optional[Dict] = None,
) -> bool:
    """
    Drops non-commercial residential pins, societies, and homes.
    """
    if osm_class in ["place"] and osm_type in ["house", "isolated_dwelling", "subdivision"]:
        return False
    if osm_class in ["building"] and osm_type in ["residential", "house", "apartments", "dormitory"]:
        return False
    if addr_details:
        bld = addr_details.get("building")
        if bld in ["residential", "house", "apartments"]:
            return False
    if not display_name or len(display_name.strip()) < 4:
        return False
    return True


def fetch_from_gmaps_browser(location: str, category: str, max_items: int = 15) -> List[Dict]:
    """
    Extracts real places directly from Google Maps search feed using Playwright.
    Captures:
    - Real business name (cleaned of emojis and icon characters)
    - Drops non-commercial entities (Villa, Apartment, Society, Bunglow, Home, Flat, Residency)
    - Layer 1 website button detection (aria-label="Website", data-value="Website", or external link)
    - Place ID and CID deep links
    - Phone extraction using Indian phone regex
    """
    candidates: List[Dict] = []
    if not HAS_PLAYWRIGHT:
        return candidates

    try:
        url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(category + ' in ' + location)}"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=12000)
            page.wait_for_timeout(2500)

            cards = page.query_selector_all('div[role="feed"] > div > div[jsaction]')
            for card in cards:
                if len(candidates) >= max_items:
                    break
                title_el = card.query_selector('.hfpxzc')
                if not title_el:
                    continue

                raw_name = title_el.get_attribute("aria-label") or ""
                name_clean = clean_business_name(raw_name)
                if not is_commercial_business(name_clean):
                    continue

                href = title_el.get_attribute("href") or ""

                # Layer 1 Website Button Check
                web_btn = card.query_selector(
                    '[data-value="Website"], [aria-label*="website" i], '
                    'a[href^="http"]:not([href*="google"]):not([href*="gstatic"])'
                )
                maps_website = web_btn.get_attribute("href") if web_btn else None
                if web_btn and not maps_website:
                    maps_website = "Active Website Button on Maps Profile"

                # Extract Place ID & CID
                place_id_m = re.search(r'!19s(ChIJ[a-zA-Z0-9_-]{20,})', href)
                place_id = place_id_m.group(1) if place_id_m else None

                cid_m = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', href)
                dec_cid = None
                if cid_m:
                    try:
                        hex_cid = cid_m.group(1).split(":")[1]
                        dec_cid = str(int(hex_cid, 16))
                    except Exception:
                        pass

                card_text = card.inner_text().replace("\n", " | ")
                area = location.split(",")[0].strip()
                text_parts = [p.strip() for p in card_text.split("|") if p.strip()]
                specific_addr = f"{name_clean}, {location}"
                for tp in text_parts:
                    if any(ind in tp.lower() for ind in ["road", "rd", "marg", "complex", "circle", "nagar", "cross", "lane", "avenue"]):
                        specific_addr = f"{tp}, {location}"
                        area = tp
                        break

                # Extract phone number using Indian phone regex
                phone = extract_indian_phone(card_text)

                maps_url = construct_maps_url(
                    name=name_clean,
                    address=specific_addr,
                    location=location,
                    place_id=place_id,
                    cid=dec_cid,
                )

                candidates.append({
                    "name": name_clean,
                    "category": category,
                    "phone": phone,
                    "address": specific_addr,
                    "area": area,
                    "maps_url": maps_url,
                    "maps_website": maps_website,
                    "place_id": place_id,
                    "cid": dec_cid,
                    "pitch_angle": get_pitch_angle(category),
                })

            browser.close()
    except Exception:
        pass

    return candidates


def fetch_from_nominatim(location: str, category: str, max_items: int = 15) -> List[Dict]:
    """
    Live real-world place discovery using OpenStreetMap Nominatim API.
    Returns real, existing businesses with real street addresses and areas.
    """
    candidates: List[Dict] = []
    headers = {"User-Agent": "LocalLeadPulse/2.0 (leadgen@localleadpulse.org)"}

    # Derive search terms from category and synonyms
    cat_lower = category.lower()
    search_terms = [f"{category} in {location}"]
    synonyms = CATEGORY_SYNONYMS.get(cat_lower, [])
    for syn in synonyms[:2]:
        search_terms.append(f"{syn} in {location}")

    seen_names: Set[str] = set()

    for term in search_terms:
        if len(candidates) >= max_items:
            break
        try:
            url = (
                f"https://nominatim.openstreetmap.org/search?"
                f"q={urllib.parse.quote(term)}&format=json&addressdetails=1&extratags=1&limit={max_items}"
            )
            res = requests.get(url, headers=headers, timeout=8.0)
            if res.status_code == 200:
                data = res.json()
                for item in data:
                    raw_name = item.get("name")
                    if not raw_name or len(raw_name.strip()) < 2:
                        continue

                    name_clean = clean_business_name(raw_name)
                    if not is_commercial_business(name_clean):
                        continue

                    osm_class = item.get("class")
                    osm_type = item.get("type")
                    addr_details = item.get("address", {})
                    display_name = item.get("display_name", f"{name_clean}, {location}")

                    if not is_valid_commercial_address(display_name, osm_class, osm_type, addr_details):
                        continue

                    if name_clean.lower() in seen_names:
                        continue
                    seen_names.add(name_clean.lower())

                    road = addr_details.get("road") or ""
                    suburb = (
                        addr_details.get("suburb")
                        or addr_details.get("neighbourhood")
                        or addr_details.get("quarter")
                        or ""
                    )
                    area = suburb or road or location.split(",")[0].strip()
                    specific_address = f"{road}, {area}".strip(", ") or display_name

                    # Direct deep link per specification
                    maps_url = construct_maps_url(
                        name=name_clean,
                        address=specific_address,
                        location=location,
                    )

                    extratags = item.get("extratags") or {}
                    phone = extract_indian_phone(
                        extratags.get("phone")
                        or extratags.get("contact:phone")
                        or extratags.get("mobile")
                        or addr_details.get("phone")
                        or addr_details.get("contact:phone")
                    )

                    website = extratags.get("website") or extratags.get("contact:website")

                    candidates.append({
                        "name": name_clean,
                        "category": category,
                        "phone": phone,
                        "address": display_name,
                        "area": area,
                        "maps_url": maps_url,
                        "maps_website": website,
                        "pitch_angle": get_pitch_angle(category),
                    })
                    if len(candidates) >= max_items:
                        break
        except Exception:
            pass

    return candidates


def fetch_from_live_search(location: str, category: str, max_items: int = 10) -> List[Dict]:
    """
    Live real-world place discovery using DuckDuckGo Search snippets.
    Discovers real operating businesses mentioned in local listings and guides.
    """
    candidates: List[Dict] = []
    if not HAS_DDGS:
        return candidates

    try:
        ddgs = DDGS()
        query = f"top {category} in {location} reviews"
        results = ddgs.text(query, max_results=max_items * 2)

        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")

            clean_title = re.sub(r"\s*-\s*(Justdial|Zomato|Swiggy|Tripadvisor|Magicpin).*", "", title, flags=re.I).strip()
            clean_title = re.sub(r"^(The\s+)?(Top\s+\d+|Best\s+\d+|\d+\s+Best)\s+", "", clean_title, flags=re.I).strip()

            if any(agg in clean_title.lower() for agg in ["garages in", "cafes in", "restaurants in", "list of", "pharmacies in"]):
                continue

            raw_name = clean_title.split("|")[0].split("-")[0].strip()
            name = clean_business_name(raw_name)
            if not is_commercial_business(name) or len(name) < 3 or len(name) > 40:
                continue

            # Extract phone number using Indian phone regex
            phone = extract_indian_phone(body)

            # Check for listed standalone website
            maps_website = None
            if not any(ex in href for ex in ["justdial", "zomato", "swiggy", "tripadvisor", "facebook", "instagram"]):
                maps_website = href

            area = location.split(",")[0].strip()
            maps_url = construct_maps_url(
                name=name,
                address=area,
                location=location,
            )

            candidates.append({
                "name": name,
                "category": category,
                "phone": phone,
                "address": f"{name}, {location}",
                "area": area,
                "maps_url": maps_url,
                "maps_website": maps_website,
                "pitch_angle": get_pitch_angle(category),
            })
            if len(candidates) >= max_items:
                break
    except Exception:
        pass

    return candidates


def fetch_places_candidates(
    location: str,
    categories: List[str],
    limit: int = 20,
    use_mock: bool = False,
    api_key: Optional[str] = None,
) -> List[Dict]:
    """
    Fetches real, live existing businesses for any requested location and categories.
    Distributes searches across all selected categories.
    Filters residential pins, extracts Indian phone numbers and direct Maps deep-links.
    """
    all_candidates: List[Dict] = []
    seen_names: Set[str] = set()

    needed_per_category = max(5, int((limit * 2.5) / max(1, len(categories))))
    by_category: Dict[str, List[Dict]] = {}

    for cat in categories:
        cat_candidates: List[Dict] = []

        # 1. Official Google Places API if configured
        if api_key and not use_mock:
            try:
                url = "https://places.googleapis.com/v1/places:searchText"
                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": (
                        "places.id,places.displayName,places.formattedAddress,"
                        "places.nationalPhoneNumber,places.websiteUri,places.googleMapsUri"
                    ),
                }
                body = {
                    "textQuery": f"{cat} in {location}",
                    "pageSize": min(needed_per_category, 20),
                }
                res = requests.post(url, headers=headers, json=body, timeout=8.0)
                if res.status_code == 200:
                    data = res.json()
                    for p in data.get("places", []):
                        raw_name = p.get("displayName", {}).get("text", "Local Business")
                        clean_n = clean_business_name(raw_name)
                        if not is_commercial_business(clean_n):
                            continue

                        place_id = p.get("id")
                        addr = p.get("formattedAddress", location)
                        phone = extract_indian_phone(p.get("nationalPhoneNumber"))
                        maps_url = construct_maps_url(
                            name=clean_n,
                            address=addr,
                            location=location,
                            place_id=place_id,
                        )
                        cat_candidates.append({
                            "name": clean_n,
                            "category": cat,
                            "phone": phone,
                            "address": addr,
                            "area": location.split(",")[0].strip(),
                            "maps_website": p.get("websiteUri"),
                            "maps_url": maps_url,
                            "place_id": place_id,
                            "pitch_angle": get_pitch_angle(cat),
                        })
            except Exception:
                pass

        # 2. Live Google Maps Browser Feed Extraction
        if len(cat_candidates) < needed_per_category and not use_mock and HAS_PLAYWRIGHT:
            gmaps_candidates = fetch_from_gmaps_browser(location, cat, max_items=needed_per_category)
            for c in gmaps_candidates:
                if c["name"].lower() not in seen_names:
                    cat_candidates.append(c)
                    seen_names.add(c["name"].lower())

        # 3. Live OpenStreetMap Nominatim Discovery
        if len(cat_candidates) < needed_per_category:
            osm_candidates = fetch_from_nominatim(location, cat, max_items=needed_per_category)
            for c in osm_candidates:
                if c["name"].lower() not in seen_names:
                    cat_candidates.append(c)
                    seen_names.add(c["name"].lower())

        # 4. Live Web Search Discovery (DDGS / Bing fallback)
        if len(cat_candidates) < needed_per_category:
            search_candidates = fetch_from_live_search(location, cat, max_items=needed_per_category)
            for c in search_candidates:
                if c["name"].lower() not in seen_names:
                    cat_candidates.append(c)
                    seen_names.add(c["name"].lower())

        by_category[cat] = cat_candidates

    # Round-robin interleave across categories
    max_len = max((len(c) for c in by_category.values()), default=0)
    for idx in range(max_len):
        for cat in categories:
            if idx < len(by_category[cat]):
                all_candidates.append(by_category[cat][idx])

    return all_candidates
