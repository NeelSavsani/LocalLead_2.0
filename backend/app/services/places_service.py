import re
import urllib.parse
from typing import Dict, List, Optional, Set
import requests

from app.config import settings

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
    "hardware": "Interactive digital product showcase with direct WhatsApp quotation",
    "hardware store": "Digital sanitaryware & architectural hardware showcase catalog",
    "boutique": "Bridal wear portfolio gallery & custom tailoring booking page",
    "salon": "Online chair booking & wedding bridal package pricing calculator",
}


def get_pitch_angle(category: str) -> str:
    cat_lower = category.lower()
    for key, pitch in CATEGORY_PITCH_ANGLES.items():
        if key in cat_lower or cat_lower in key:
            return pitch
    return f"Digital storefront & direct customer booking portal for {category}"


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
                f"q={urllib.parse.quote(term)}&format=json&addressdetails=1&limit={max_items}"
            )
            res = requests.get(url, headers=headers, timeout=8.0)
            if res.status_code == 200:
                data = res.json()
                for item in data:
                    name = item.get("name")
                    if not name or len(name.strip()) < 2:
                        continue

                    # Filter out generic admin area names
                    name_clean = name.strip()
                    if name_clean.lower() in seen_names:
                        continue
                    seen_names.add(name_clean.lower())

                    display_name = item.get("display_name", f"{name_clean}, {location}")
                    addr_details = item.get("address", {})
                    area = (
                        addr_details.get("suburb")
                        or addr_details.get("neighbourhood")
                        or addr_details.get("quarter")
                        or addr_details.get("road")
                        or location.split(",")[0].strip()
                    )

                    # Exact Google Maps query URL per specification:
                    # https://www.google.com/maps/search/?api=1&query={encoded_name}+{encoded_location}
                    maps_url = (
                        f"https://www.google.com/maps/search/?api=1&query="
                        f"{urllib.parse.quote_plus(name_clean)}+{urllib.parse.quote_plus(location)}"
                    )

                    phone = addr_details.get("phone") or addr_details.get("contact:phone") or "N/A"
                    website = item.get("extratags", {}).get("website") if item.get("extratags") else None

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

            # Extract business name from title patterns like "Business Name - Location" or "Top X in Location"
            # If title is an aggregator directory page, skip or parse
            clean_title = re.sub(r"\s*-\s*(Justdial|Zomato|Swiggy|Tripadvisor|Magicpin).*", "", title, flags=re.I).strip()
            clean_title = re.sub(r"^(The\s+)?(Top\s+\d+|Best\s+\d+|\d+\s+Best)\s+", "", clean_title, flags=re.I).strip()

            # Skip pure directory aggregate titles
            if any(agg in clean_title.lower() for agg in ["garages in", "cafes in", "restaurants in", "list of"]):
                continue

            name = clean_title.split("|")[0].split("-")[0].strip()
            if len(name) < 3 or len(name) > 40:
                continue

            # Extract phone number if present in body snippet
            phone_match = re.search(r"(\+91[\s-]?[6-9]\d{9}|[6-9]\d{9})", body)
            phone = phone_match.group(1) if phone_match else "N/A"

            # Check for listed standalone website
            maps_website = None
            if not any(ex in href for ex in ["justdial", "zomato", "swiggy", "tripadvisor", "facebook"]):
                maps_website = href

            maps_url = (
                f"https://www.google.com/maps/search/?api=1&query="
                f"{urllib.parse.quote_plus(name)}+{urllib.parse.quote_plus(location)}"
            )

            candidates.append({
                "name": name,
                "category": category,
                "phone": phone,
                "address": f"{name}, {location}",
                "area": location.split(",")[0].strip(),
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
    Completely removes static/dummy fallback data.
    """
    all_candidates: List[Dict] = []
    seen_names: Set[str] = set()

    # Determine candidates needed per category to satisfy target limit with 2-layer filter
    needed_per_category = max(5, int((limit * 2.5) / max(1, len(categories))))

    # Collect candidates by category
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
                        name = p.get("displayName", {}).get("text", "Local Business")
                        maps_url = (
                            f"https://www.google.com/maps/search/?api=1&query="
                            f"{urllib.parse.quote_plus(name)}+{urllib.parse.quote_plus(location)}"
                        )
                        cat_candidates.append({
                            "name": name,
                            "category": cat,
                            "phone": p.get("nationalPhoneNumber", "N/A"),
                            "address": p.get("formattedAddress", f"{location}"),
                            "area": location.split(",")[0].strip(),
                            "maps_website": p.get("websiteUri"),
                            "maps_url": maps_url,
                            "pitch_angle": get_pitch_angle(cat),
                        })
            except Exception:
                pass

        # 2. Live OpenStreetMap Nominatim Discovery
        if len(cat_candidates) < needed_per_category:
            osm_candidates = fetch_from_nominatim(location, cat, max_items=needed_per_category)
            for c in osm_candidates:
                if c["name"].lower() not in seen_names:
                    cat_candidates.append(c)
                    seen_names.add(c["name"].lower())

        # 3. Live Web Search Discovery (DDGS / Bing fallback)
        if len(cat_candidates) < needed_per_category:
            search_candidates = fetch_from_live_search(location, cat, max_items=needed_per_category)
            for c in search_candidates:
                if c["name"].lower() not in seen_names:
                    cat_candidates.append(c)
                    seen_names.add(c["name"].lower())

        by_category[cat] = cat_candidates

    # Round-robin interleave across categories for balanced representation
    max_len = max((len(c) for c in by_category.values()), default=0)
    for idx in range(max_len):
        for cat in categories:
            if idx < len(by_category[cat]):
                all_candidates.append(by_category[cat][idx])

    return all_candidates
