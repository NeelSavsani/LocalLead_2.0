import logging
import re
import unicodedata
import urllib.parse
import hashlib
from typing import Dict, List, Optional, Set
import requests
import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.models.schemas import clean_business_name, is_commercial_business

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

logger = logging.getLogger(__name__)

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

# Strict listicle & blog keywords to instantly reject aggregator / guide headlines
LISTICLE_KEYWORDS: List[str] = [
    "top ",
    "best ",
    "list of",
    "cafes in",
    "shops in",
    "near me",
    "10 best",
    "restaurants in",
    "garages in",
    "bars in",
    "pubs in",
    "places in",
    "guide to",
]

# Accurate Indian Phone Number Pattern per specification:
# (?:\+91[\-\s]?)?[0]?[6-9]\d{9}|0\d{2,4}[\-\s]?\d{6,8} (with space-separated 5-digit block support)
INDIAN_PHONE_REGEX = re.compile(
    r'(?:(?:\+91[\-\s]?)?[0]?[6-9]\d{9}|(?:\+91[\-\s]?)?[0]?[6-9]\d{4}[\-\s]?\d{5}|0\d{2,4}[\-\s]?\d{6,8})'
)


def is_listicle_title(name: str) -> bool:
    """
    Strict title validator that instantly discards any name containing listicle keywords:
    ['top ', 'best ', 'list of', 'cafes in', 'shops in', 'near me', '10 best', 'restaurants in', 'garages in']
    Handles unicode normalization (e.g. Cafés -> cafes).
    """
    if not name or len(name.strip()) < 2:
        return True
    # Normalize unicode to decompose accents (e.g. Cafés -> Cafes)
    norm = "".join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c)).lower()
    norm = f" {norm.strip()} "
    for kw in LISTICLE_KEYWORDS:
        if kw in norm:
            return True
    return False


def get_pitch_angle(category: str) -> str:
    cat_lower = category.lower()
    for key, pitch in CATEGORY_PITCH_ANGLES.items():
        if key in cat_lower or cat_lower in key:
            return pitch
    return f"Digital storefront & direct customer booking portal for {category}"


def extract_indian_phone(text: Optional[str]) -> str:
    r"""
    Extracts Indian phone numbers from text using standard regex:
    (?:\+91[\-\s]?)?[0]?[6-9]\d{9}|0\d{2,4}[\-\s]?\d{6,8}
    Handles both compacted and space-separated formatting.
    """
    if not text:
        return "N/A"

    # 1. First check raw text directly with INDIAN_PHONE_REGEX
    raw_matches = INDIAN_PHONE_REGEX.findall(str(text))
    for m in raw_matches:
        clean = re.sub(r'[\s-]', '', m)
        if clean.startswith(('00', '19', '20')):
            continue
        if len(clean) in [10, 11, 12, 13]:
            return m.strip()

    # 2. Try after collapsing internal whitespace between digits (e.g. '085305 26269' -> '08530526269')
    normalized = re.sub(r'(?<=\d)\s+(?=\d)', '', str(text))
    matches = INDIAN_PHONE_REGEX.findall(normalized)
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
    direct_url: Optional[str] = None,
) -> str:
    """
    Constructs an exact direct Google Maps deep-link per specification:
    - If direct_url is captured: returns direct place URL (https://www.google.com/maps/place/...)
    - If place_id is captured: https://www.google.com/maps/place/?q=place_id:{place_id}
    - If CID is captured: https://maps.google.com/?cid={cid}
    This deliberately has no search-query fallback.  A search result page is not a
    stable link to a particular business drawer.
    """
    if direct_url and "google.com/maps/place/" in direct_url:
        return direct_url
    if place_id and len(place_id.strip()) > 5:
        return f"https://www.google.com/maps/place/?q=place_id:{urllib.parse.quote_plus(place_id.strip())}"
    if cid and len(cid.strip()) > 3:
        return f"https://maps.google.com/?cid={urllib.parse.quote_plus(cid.strip())}"

    return ""


def is_direct_place_url(url: Optional[str]) -> bool:
    """Return whether *url* opens one exact Google Maps place drawer."""
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    return (
        (host.endswith("google.com") and "/maps/place/" in parsed.path)
        or (host == "maps.google.com" and "cid=" in parsed.query)
    )


def extract_coordinates_from_url(url: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    if not url:
        return None, None
    m = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _get_fallback_coordinates(location: str, name: str) -> tuple[Optional[float], Optional[float]]:
    loc_lower = location.lower()
    centers = {
        "surat": (21.1702, 72.8311),
        "ahmedabad": (23.0225, 72.5714),
        "rajkot": (22.3039, 70.8022),
        "gandhinagar": (23.2156, 72.6369)
    }
    
    base_lat, base_lon = None, None
    for city, coords in centers.items():
        if city in loc_lower:
            base_lat, base_lon = coords
            break
            
    if base_lat is None:
        return None, None
        
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    offset_lat = ((h % 2000) - 1000) / 100000.0
    offset_lon = (((h // 2000) % 2000) - 1000) / 100000.0
    
    return base_lat + offset_lat, base_lon + offset_lon


def extract_drawer_phone(page) -> str:
    """Extract a phone from an already-open Google Maps place drawer."""
    selectors = (
        '[data-item-id^="phone:"], a[href^="tel:"], '
        '[aria-label^="Phone:" i], [data-dtype="d3ph"]'
    )
    for element in page.query_selector_all(selectors):
        values = (
            element.get_attribute("data-item-id"),
            element.get_attribute("href"),
            element.get_attribute("aria-label"),
            element.inner_text(),
        )
        for value in values:
            phone = extract_indian_phone(value)
            if phone != "N/A":
                return phone
    main = page.query_selector('div[role="main"]')
    return extract_indian_phone(main.inner_text()) if main else "N/A"


def extract_place_identifiers(container) -> tuple[Optional[str], Optional[str]]:
    """Read CID/Place ID attributes from a Maps card or its containing node."""
    cid = container.get_attribute("data-cid")
    place_id = container.get_attribute("data-place-id")
    for element in container.query_selector_all("a[data-cid], a[data-place-id], [data-cid], [data-place-id]"):
        cid = cid or element.get_attribute("data-cid")
        place_id = place_id or element.get_attribute("data-place-id")
    return cid, place_id


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


def _deprecated_sync_fetch_from_gmaps_browser(location: str, category: str, max_items: int = 15) -> List[Dict]:
    """
    Extracts real places directly from Google Local Place Cards / Google Maps using Playwright.

    1. Target Real Google Local Place Cards:
       - Query Google Local listings using the Local Pack endpoint:
         https://www.google.com/search?q={category}+in+{location}&tbm=lcl&hl=en
       - If captcha/blocked or empty, queries direct Google Maps search cards:
         https://www.google.com/maps/search/{category}+in+{location}
       - Extracts actual individual businesses (e.g. "Gigil Cafe", "Hideout Cafe & Food", "Tea Post").

    2. Extract True Place Attributes:
       - Business Name: from div.dbg0pd, div[role="heading"], or a.hfpxzc[aria-label].
       - Direct Place URL: direct Google Maps URL (https://www.google.com/maps/place/...) containing CID or coordinates.
       - Phone Number: extracted directly from place snippet using regex. If no phone visible on snippet, query place card drawer.
       - Layer 1 Website Detection: Check if card/drawer contains active "Website" link (a[aria-label*="Website"], a.yY1vvd, etc.).
       - Reject Listicles: strictly discard names matching LISTICLE_KEYWORDS.
    """
    candidates: List[Dict] = []
    if not HAS_PLAYWRIGHT:
        return candidates

    seen_names: Set[str] = set()

    try:
        # This implementation is intentionally disabled.  The async function
        # below is the only scraper entry point used by FastAPI.
        raise RuntimeError("Synchronous Playwright scraping is disabled")
        if False:  # pragma: no cover - retained only as historical reference
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-US"
            )
            page = context.new_page()

            # 1. Attempt Google Local Pack endpoint
            local_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(category + ' in ' + location)}&tbm=lcl&hl=en"
            use_maps = False
            try:
                page.goto(local_url, timeout=12000)
                page.wait_for_timeout(2000)
                if "/sorry/" in page.url or "consent.google.com" in page.url:
                    use_maps = True
                else:
                    local_cards = page.query_selector_all('div.VkpGBb, div.C8TUKc, div[jscontroller="AtSb"]')
                    if not local_cards:
                        use_maps = True
                    else:
                        for l_card in local_cards:
                            if len(candidates) >= max_items:
                                break
                            title_el = l_card.query_selector('div.dbg0pd, div[role="heading"], a.vw7Du')
                            if not title_el:
                                continue
                            raw_name = title_el.inner_text().strip()
                            name_clean = clean_business_name(raw_name)
                            if not name_clean or is_listicle_title(name_clean) or not is_commercial_business(name_clean):
                                continue
                            if name_clean.lower() in seen_names:
                                continue
                            seen_names.add(name_clean.lower())

                            # Layer 1 Website Detection on Local card
                            web_btn = l_card.query_selector(
                                'a[aria-label*="Website" i], a.yY1vvd, a[data-value="Website"], a:has-text("Website")'
                            )
                            maps_website = web_btn.get_attribute("href") if web_btn else None
                            if web_btn and not maps_website:
                                maps_website = "Active Website Button on Local Card"

                            snippet_text = l_card.inner_text().replace("\n", " ")
                            # A snippet is not authoritative.  Every candidate is
                            # opened below and the drawer is the phone source.
                            phone = "N/A"

                            # Direct place link & CID
                            link_el = l_card.query_selector('a[href*="/maps/place/"], a[data-cid], a[data-place-id], a.vw7Du')
                            href = link_el.get_attribute("href") if link_el else ""
                            data_cid, data_place_id = extract_place_identifiers(l_card)

                            # Open every card's drawer; phone and canonical URL
                            # must come from the individual place, never its list row.
                            try:
                                title_el.click()
                                page.wait_for_timeout(1200)
                                phone = extract_drawer_phone(page)
                                href = page.url if "/maps/place/" in page.url else href
                                drawer = page.query_selector('div[role="main"]')
                                if drawer:
                                    drawer_cid, drawer_place_id = extract_place_identifiers(drawer)
                                    data_cid = data_cid or drawer_cid
                                    data_place_id = data_place_id or drawer_place_id
                                if not maps_website:
                                    w_el = page.query_selector('a[data-item-id="authority"], a[aria-label*="Website" i], a[data-tooltip*="Open website" i]')
                                    if w_el:
                                        maps_website = w_el.get_attribute("href")
                            except Exception:
                                pass

                            direct_maps_url = construct_maps_url(
                                name=name_clean,
                                address=snippet_text,
                                location=location,
                                place_id=data_place_id,
                                cid=data_cid,
                                direct_url=href if "/maps/place/" in href else None,
                            )

                            if phone == "N/A" or not is_direct_place_url(direct_maps_url):
                                continue

                            candidates.append({
                                "name": name_clean,
                                "category": category,
                                "phone": phone,
                                "address": f"{name_clean}, {location}",
                                "area": location.split(",")[0].strip(),
                                "maps_url": direct_maps_url,
                                "maps_website": maps_website,
                                "cid": data_cid,
                                "pitch_angle": get_pitch_angle(category),
                            })
            except Exception:
                use_maps = True

            # 2. Fallback or primary Google Maps search cards
            if use_maps or len(candidates) < max_items:
                maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(category + ' in ' + location)}"
                page.goto(maps_url, timeout=25000)
                page.wait_for_timeout(2500)

                feed = page.query_selector('div[role="feed"]')
                if feed:
                    scroll_count = max(1, min(4, max_items // 4))
                    for _ in range(scroll_count):
                        page.evaluate('el => el.scrollBy(0, 1200)', feed)
                        page.wait_for_timeout(700)

                cards = page.query_selector_all('div.Nv2PK')
                staged_items = []
                for card in cards:
                    title_el = card.query_selector('a.hfpxzc, div.dbg0pd, div[role="heading"]')
                    if not title_el:
                        continue
                    raw_name = title_el.get_attribute("aria-label") or title_el.inner_text().strip()
                    name_clean = clean_business_name(raw_name)
                    if not name_clean or is_listicle_title(name_clean) or not is_commercial_business(name_clean):
                        continue
                    if name_clean.lower() in seen_names:
                        continue
                    seen_names.add(name_clean.lower())

                    href = title_el.get_attribute("href") or ""
                    card_text = card.inner_text().replace("\n", " ")

                    # Layer 1 Website Detection on card
                    web_btn = card.query_selector(
                        'a[aria-label*="Website" i], a.yY1vvd, a[data-value="Website"], a:has-text("Website")'
                    )
                    maps_website = web_btn.get_attribute("href") if web_btn else None
                    if web_btn and not maps_website:
                        maps_website = "Active Website Button on Maps Profile"

                    phone = "N/A"
                    cid, place_id = extract_place_identifiers(card)

                    staged_items.append({
                        "name": name_clean,
                        "href": href,
                        "phone": phone,
                        "cid": cid,
                        "place_id": place_id,
                        "maps_website": maps_website,
                        "card_text": card_text,
                    })
                    if len(candidates) + len(staged_items) >= max_items * 2:
                        break

                # Resolve drawer details for staged items
                for idx, item in enumerate(staged_items):
                    if len(candidates) >= max_items:
                        break
                    name = item["name"]
                    phone = item["phone"]
                    maps_website = item["maps_website"]
                    direct_url = item["href"]
                    specific_addr = f"{name}, {location}"

                    try:
                        # Navigate through the card's place URL when available;
                        # it opens the same drawer without relying on a stale list
                        # index after previous drawer navigations.
                        if "/maps/place/" in direct_url:
                            page.goto(direct_url, timeout=15000)
                        else:
                            loc = page.locator('a.hfpxzc').nth(idx)
                            loc.scroll_into_view_if_needed()
                            loc.click()
                        page.wait_for_timeout(1000)

                        if "/maps/place/" in page.url:
                            direct_url = page.url

                        phone = extract_drawer_phone(page)

                        # Drawer website detection
                        if not maps_website:
                            d_web = page.query_selector(
                                'a[data-item-id="authority"], a[aria-label*="Website" i], a[data-tooltip*="Open website" i]'
                            )
                            if d_web:
                                maps_website = d_web.get_attribute("href")

                        # Drawer address extraction
                        addr_el = page.query_selector('[data-item-id="address"], button[aria-label^="Address:" i]')
                        if addr_el:
                            raw_addr = addr_el.get_attribute("aria-label") or addr_el.inner_text()
                            specific_addr = re.sub(r'^(Address:\s*|\s*)', '', raw_addr).strip()

                    except Exception:
                        pass

                    # Place ID and CID parsing from direct URL
                    place_id_m = re.search(r'!19s(ChIJ[a-zA-Z0-9_-]{20,})', direct_url)
                    place_id = place_id_m.group(1) if place_id_m else None
                    cid_m = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', direct_url)
                    dec_cid = None
                    if cid_m:
                        try:
                            dec_cid = str(int(cid_m.group(1).split(":")[1], 16))
                        except Exception:
                            pass

                    area = location.split(",")[0].strip()

                    maps_url = construct_maps_url(name, place_id=place_id or item.get("place_id"), cid=dec_cid or item.get("cid"), direct_url=direct_url)
                    if phone == "N/A" or not is_direct_place_url(maps_url):
                        continue
                    candidates.append({
                        "name": name,
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
    except Exception as e:
        logger.warning(f"Error scraping Google Maps/Local: {e}")

    return candidates


async def _async_drawer_phone(page) -> str:
    for element in await page.query_selector_all(
        '[data-item-id^="phone:"], a[href^="tel:"], [aria-label^="Phone:" i], [data-dtype="d3ph"]'
    ):
        for value in (
            await element.get_attribute("data-item-id"),
            await element.get_attribute("href"),
            await element.get_attribute("aria-label"),
            await element.inner_text(),
        ):
            phone = extract_indian_phone(value)
            if phone != "N/A":
                return phone
    main = await page.query_selector('div[role="main"]')
    return extract_indian_phone(await main.inner_text()) if main else "N/A"


async def _http_local_cards_fallback(location: str, category: str, max_items: int) -> List[Dict]:
    """Best-effort, crash-safe Local Pack fallback when Chromium cannot start."""
    query = urllib.parse.quote_plus(f"{category} in {location}")
    url = f"https://www.google.com/search?q={query}&tbm=lcl&hl=en"
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Google Local Pack HTTP fallback unavailable: %s", exc)
        return []

    candidates: List[Dict] = []
    soup = BeautifulSoup(response.text, "html.parser")
    for card in soup.select("div.VkpGBb, div.C8TUKc, div[jscontroller='AtSb']"):
        title = card.select_one("div.dbg0pd, div[role='heading'], a.vw7Du")
        link = card.select_one("a[href*='/maps/place/'], a[data-cid], a[data-place-id]")
        if not title or not link:
            continue
        name = clean_business_name(title.get_text(" ", strip=True))
        phone = extract_indian_phone(card.get_text(" ", strip=True))
        href = urllib.parse.urljoin("https://www.google.com", link.get("href") or "")
        cid = link.get("data-cid") or card.get("data-cid")
        place_id = link.get("data-place-id") or card.get("data-place-id")
        maps_url = construct_maps_url(name, place_id=place_id, cid=cid, direct_url=href)
        if not name or phone == "N/A" or not is_direct_place_url(maps_url):
            continue
        lat, lon = extract_coordinates_from_url(href)
        if lat is None:
            lat, lon = _get_fallback_coordinates(location, name)
        candidates.append({
            "name": name, "category": category, "phone": phone,
            "address": f"{name}, {location}", "area": location.split(",")[0].strip(),
            "latitude": lat, "longitude": lon,
            "maps_url": maps_url, "maps_website": None, "pitch_angle": get_pitch_angle(category),
        })
        if len(candidates) >= max_items:
            break
    return candidates


async def fetch_from_gmaps_browser(location: str, category: str, max_items: int = 15) -> List[Dict]:
    """Async Google Maps drawer scraper; browser failures fall back to Local Pack HTTP."""
    if not HAS_PLAYWRIGHT:
        return await _http_local_cards_fallback(location, category, max_items)

    candidates: List[Dict] = []
    seen: Set[str] = set()
    search_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(category + ' in ' + location)}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                locale="en-US",
            )
            page = await context.new_page()
            await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            feed = await page.query_selector('div[role="feed"]')
            if feed:
                for _ in range(max(1, min(4, max_items // 4))):
                    await feed.evaluate("el => el.scrollBy(0, 1200)")
                    await page.wait_for_timeout(600)

            staged: List[tuple[str, str]] = []
            for card in await page.query_selector_all("div.Nv2PK"):
                title = await card.query_selector("a.hfpxzc")
                if not title:
                    continue
                name = clean_business_name((await title.get_attribute("aria-label")) or await title.inner_text())
                if not name or name.lower() in seen or is_listicle_title(name) or not is_commercial_business(name):
                    continue
                href = await title.get_attribute("href") or ""
                if "/maps/place/" not in href:
                    continue
                seen.add(name.lower())
                staged.append((name, href))
                if len(staged) >= max_items:
                    break

            # Collect links before navigating.  Navigating while iterating card
            # ElementHandles invalidates the remaining handles in Chromium.
            for name, href in staged:
                try:
                    await page.goto(href, timeout=15000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(800)
                    phone = await _async_drawer_phone(page)
                    direct_url = page.url if "/maps/place/" in page.url else href
                    website = await page.query_selector('a[data-item-id="authority"], a[aria-label*="Website" i]')
                    maps_website = await website.get_attribute("href") if website else None
                    address_el = await page.query_selector('[data-item-id="address"], button[aria-label^="Address:" i]')
                    address = (await address_el.get_attribute("aria-label") or await address_el.inner_text()) if address_el else f"{name}, {location}"
                    maps_url = construct_maps_url(name, direct_url=direct_url)
                    if phone == "N/A" or not is_direct_place_url(maps_url):
                        continue
                    lat, lon = extract_coordinates_from_url(direct_url)
                    if lat is None:
                        lat, lon = _get_fallback_coordinates(location, name)
                    candidates.append({
                        "name": name, "category": category, "phone": phone, "address": address,
                        "area": location.split(",")[0].strip(), "latitude": lat, "longitude": lon, "maps_url": maps_url,
                        "maps_website": maps_website, "pitch_angle": get_pitch_angle(category),
                    })
                except Exception as exc:
                    logger.debug("Unable to resolve Google Maps drawer for %s: %s", name, exc)
            await context.close()
            await browser.close()
            return candidates
    except Exception as exc:
        logger.warning("Async Google Maps browser unavailable; using HTTP fallback: %s", exc)
        return await _http_local_cards_fallback(location, category, max_items)


def fetch_from_nominatim(location: str, category: str, max_items: int = 15) -> List[Dict]:
    """
    Live real-world place discovery using OpenStreetMap Nominatim API.
    Returns real, existing businesses with real street addresses and areas.
    """
    candidates: List[Dict] = []
    headers = {"User-Agent": "LocalLeadPulse/2.0 (leadgen@localleadpulse.org)"}

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
                    if not is_commercial_business(name_clean) or is_listicle_title(name_clean):
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

                    try:
                        lat = float(item.get("lat")) if item.get("lat") else None
                        lon = float(item.get("lon")) if item.get("lon") else None
                    except (ValueError, TypeError):
                        lat, lon = None, None
                    if lat is None:
                        lat, lon = _get_fallback_coordinates(location, name_clean)

                    candidates.append({
                        "name": name_clean,
                        "category": category,
                        "phone": phone,
                        "address": display_name,
                        "area": area,
                        "latitude": lat,
                        "longitude": lon,
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
    Strictly filters out listicles and blog headlines.
    """
    candidates: List[Dict] = []
    if not HAS_DDGS:
        return candidates

    try:
        ddgs = DDGS()
        query = f"{category} in {location}"
        results = ddgs.text(query, max_results=max_items * 2)

        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")

            clean_title = re.sub(r"\s*-\s*(Justdial|Zomato|Swiggy|Tripadvisor|Magicpin).*", "", title, flags=re.I).strip()
            clean_title = re.sub(r"^(The\s+)?(Top\s+\d+|Best\s+\d+|\d+\s+Best)\s+", "", clean_title, flags=re.I).strip()

            if any(blog_kw in href.lower() for blog_kw in ["/blog/", "/article/", "/posts/", "/city-guide/", "/places/", "/top-", "/best-"]):
                continue

            if is_listicle_title(clean_title):
                continue

            raw_name = clean_title.split("|")[0].split("-")[0].strip()
            name = clean_business_name(raw_name)
            if not is_commercial_business(name) or is_listicle_title(name) or len(name) < 3 or len(name) > 40:
                continue

            phone = extract_indian_phone(body)

            maps_website = None
            if not any(ex in href for ex in ["justdial", "zomato", "swiggy", "tripadvisor", "facebook", "instagram"]):
                maps_website = href

            area = location.split(",")[0].strip()
            maps_url = construct_maps_url(
                name=name,
                address=area,
                location=location,
            )

            lat, lon = _get_fallback_coordinates(location, name)

            candidates.append({
                "name": name,
                "category": category,
                "phone": phone,
                "address": f"{name}, {location}",
                "area": area,
                "latitude": lat,
                "longitude": lon,
                "maps_url": maps_url,
                "maps_website": maps_website,
                "pitch_angle": get_pitch_angle(category),
            })
            if len(candidates) >= max_items:
                break
    except Exception:
        pass

    return candidates


async def fetch_places_candidates(
    location: str,
    categories: List[str],
    limit: int = 20,
    use_mock: bool = False,
    api_key: Optional[str] = None,
) -> List[Dict]:
    """
    Fetches real, live existing businesses for any requested location and categories.
    Distributes searches across all selected categories.
    Filters residential pins and listicles, extracts Indian phone numbers and direct Maps deep-links.
    """
    all_candidates: List[Dict] = []
    seen_names: Set[str] = set()

    needed_per_category = max(5, int((limit * 1.5) / max(1, len(categories))))
    by_category: Dict[str, List[Dict]] = {}

    # Deterministic offline fixtures keep test scans independent of Google rate
    # limits while preserving the same two non-negotiable output guarantees.
    mock_names = ["Kesar", "Saffron", "Bluebell", "Mango Tree", "Rangoli", "Tulsi"]

    for cat in categories:
        cat_candidates: List[Dict] = []

        if use_mock:
            area = location.split(",")[0].strip()
            for index, prefix in enumerate(mock_names[:needed_per_category], start=1):
                name = f"{prefix} {cat}".strip()
                cid = str(13000000000000000000 + index + len(cat))
                cat_candidates.append({
                    "name": name,
                    "category": cat,
                    "phone": f"+91 98765 {43000 + index:05d}",
                    "address": f"{index} Market Road, {area}",
                    "area": area,
                    "latitude": 21.1702 + (index * 0.01),
                    "longitude": 72.8311 + (index * 0.01),
                    "maps_url": construct_maps_url(name, cid=cid),
                    "cid": cid,
                    "maps_website": None,
                    "search_links": [f"https://www.justdial.com/{area}/{urllib.parse.quote_plus(name)}"],
                    "pitch_angle": get_pitch_angle(cat),
                })

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
                        if not is_commercial_business(clean_n) or is_listicle_title(clean_n):
                            continue

                        place_id = p.get("id")
                        addr = p.get("formattedAddress", location)
                        phone = extract_indian_phone(p.get("nationalPhoneNumber"))
                        direct_url = p.get("googleMapsUri")

                        loc = p.get("location", {})
                        lat = loc.get("latitude")
                        lon = loc.get("longitude")

                        maps_url = construct_maps_url(
                            name=clean_n,
                            address=addr,
                            location=location,
                            place_id=place_id,
                            direct_url=direct_url,
                        )
                        cat_candidates.append({
                            "name": clean_n,
                            "category": cat,
                            "phone": phone,
                            "address": addr,
                            "area": location.split(",")[0].strip(),
                            "latitude": lat,
                            "longitude": lon,
                            "maps_website": p.get("websiteUri"),
                            "maps_url": maps_url,
                            "place_id": place_id,
                            "pitch_angle": get_pitch_angle(cat),
                        })
            except Exception:
                pass

        # 2. Live Google Maps / Local Place Cards Browser Feed Extraction.
        # fetch_from_gmaps_browser owns the HTTP fallback, including when the
        # Playwright package or browser binary is not available.
        if len(cat_candidates) < needed_per_category and not use_mock:
            gmaps_candidates = await fetch_from_gmaps_browser(location, cat, max_items=needed_per_category)
            for c in gmaps_candidates:
                if c["name"].lower() not in seen_names:
                    cat_candidates.append(c)
                    seen_names.add(c["name"].lower())

        # Nominatim and web-search results do not supply a Google place identity.
        # Do not fabricate a Maps search URL for them: it would not be a direct
        # drawer link and has no drawer-backed phone verification.

        by_category[cat] = cat_candidates

    # Round-robin interleave across categories
    max_len = max((len(c) for c in by_category.values()), default=0)
    for idx in range(max_len):
        for cat in categories:
            if idx < len(by_category[cat]):
                all_candidates.append(by_category[cat][idx])

    return all_candidates
