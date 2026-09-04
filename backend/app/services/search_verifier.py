import re
import urllib.parse
import base64
from typing import Dict, List, Optional, Set
import requests
from bs4 import BeautifulSoup


# Comprehensive Aggregator, Directory, Social, and Listing Network Blacklist
EXCLUDED_DOMAINS: Set[str] = {
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "justdial.com",
    "indiamart.com",
    "sulekha.com",
    "tradeindia.com",
    "yellowpages.in",
    "zomato.com",
    "swiggy.com",
    "magicbricks.com",
    "99acres.com",
    "tripadvisor.com",
    "tripadvisor.in",
    "magicpin.in",
    "jdmagicbox.com",
    "quikr.com",
    "olx.in",
    "wikipedia.org",
    "google.com",
    "maps.google.com",
    "goo.gl",
    "whatsapp.com",
    "wa.me",
    "pinterest.com",
    "reddit.com",
    "threads.net",
    "yelp.com",
    "indiatimes.com",
    "dialme.com",
    "locanto.com",
    "nic.in",
    "gov.in",
    "carchhe.com",
    "zigwheels.com",
    "bikewale.com",
    "carwale.com",
    "cardekho.com",
    "threebestrated.in",
    "idbf.in",
    "bizdir24.com",
    "bdir.in",
    "travelroach.com",
    "wanderlog.com",
    "datagemba.com",
    "travell.cc",
    "lbb.in",
    "whatshot.in",
    "curlytales.com",
    "holidify.com",
    "fabhotels.com",
    "treebo.com",
    "makemytrip.com",
    "goibibo.com",
}


def normalize_domain(url: str) -> str:
    """
    Extracts the root/registrable domain from a URL, stripping scheme,
    www prefix, ports, and paths.
    """
    if not url:
        return ""
    
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def is_blacklisted_domain(domain: str) -> bool:
    """
    Checks if a domain matches or is a subdomain of any excluded directory/aggregator.
    """
    domain = normalize_domain(domain)
    if not domain:
        return True

    for excluded in EXCLUDED_DOMAINS:
        if domain == excluded or domain.endswith("." + excluded):
            return True
    return False


def is_brand_domain_match(domain: str, business_name: str) -> bool:
    """
    Checks if a discovered non-blacklisted domain actually belongs to the business brand.
    e.g. 'patelautospares.in' matches 'Patel Auto Spares',
    whereas an unrelated blog or competitor domain does not.
    """
    domain_name = domain.split(".")[0].lower()
    clean_name = re.sub(r"[^\w\s]", "", business_name).lower()
    tokens = [
        t for t in clean_name.split()
        if len(t) > 2 and t not in [
            "the", "and", "center", "centre", "services", "works",
            "near", "shop", "care", "mart", "store", "repair", "hub"
        ]
    ]
    if not tokens:
        return False
    if len(tokens) >= 2:
        brand_slug = "".join(tokens[:2])
        if brand_slug in domain_name or (tokens[0] in domain_name and tokens[1] in domain_name):
            return True
        return False
    else:
        return len(tokens[0]) >= 4 and tokens[0] in domain_name


def query_live_search(query: str, max_results: int = 5) -> List[str]:
    """
    Fast live organic web search using direct HTTP requests with strict timeouts.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    try:
        resp = requests.get(url, headers=headers, timeout=2.5)
        urls: List[str] = []
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for h2 in soup.select("li.b_algo h2 a"):
                href = h2.get("href", "")
                if "/ck/a?" in href and "u=" in href:
                    m = re.search(r"[?&]u=([^&]+)", href)
                    if m:
                        raw_u = m.group(1)
                        if raw_u.startswith("a1"):
                            b64_part = raw_u[2:]
                            padded = b64_part + "=" * (-len(b64_part) % 4)
                            try:
                                decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
                                urls.append(decoded)
                            except Exception:
                                pass
                elif href.startswith("http"):
                    urls.append(href)
                if len(urls) >= max_results:
                    break
        return urls
    except Exception:
        return []


def verify_independent_website(
    business_name: str,
    location: str,
    mock_urls: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    search_engine_id: Optional[str] = None,
) -> Dict[str, any]:
    """
    Layer 2 Verification Engine:
    Queries real live search engines for `"{Business Name}" "{Location}"`.
    Evaluates top 5 organic search results:
    - Filters out directory/social/aggregator links.
    - If an independent, non-blacklisted domain matching the business brand is found -> DISQUALIFIED.
    - If only blacklisted directory results or no brand domain is found -> QUALIFIED lead.
    """
    detected_standalone_urls: List[str] = []
    all_candidate_urls: List[str] = []

    # Priority 1: Injected mock results (for unit tests)
    if mock_urls is not None:
        all_candidate_urls = mock_urls[:5]
        for url in all_candidate_urls:
            domain = normalize_domain(url)
            if not is_blacklisted_domain(domain):
                detected_standalone_urls.append(url)

    # Priority 2: Google Custom Search API if keys are provided
    elif api_key and search_engine_id:
        try:
            cse_url = "https://www.googleapis.com/customsearch/v1"
            # Keep both queries clean: street and landmark fragments bury a
            # chain's official domain under local directory results.
            for query in (f'"{business_name}"', f'"{business_name}" "{location}"'):
                params = {"key": api_key, "cx": search_engine_id, "q": query, "num": 5}
                res = requests.get(cse_url, params=params, timeout=4.0)
                if res.status_code == 200:
                    for item in res.json().get("items", []):
                        link = item.get("link")
                        if link and link not in all_candidate_urls:
                            all_candidate_urls.append(link)
        except Exception:
            all_candidate_urls = []

    # Priority 3: Real Live Web Search
    if not all_candidate_urls and mock_urls is None:
        clean_name = re.sub(r"[^\w\s]", "", business_name).strip()
        clean_loc = re.sub(r"[^\w\s]", "", location.split(",")[0]).strip()
        # Search both the brand alone and the brand plus city; this catches chain
        # homepages (for example cafecoffeeday.com) without address noise.
        all_candidate_urls = query_live_search(f'"{clean_name}"', max_results=5)
        if clean_loc:
            all_candidate_urls.extend(query_live_search(f'"{clean_name}" "{clean_loc}"', max_results=5))
        all_candidate_urls = list(dict.fromkeys(all_candidate_urls))

    if mock_urls is None:
        for url in all_candidate_urls:
            domain = normalize_domain(url)
            if not domain:
                continue
            if not is_blacklisted_domain(domain) and is_brand_domain_match(domain, business_name):
                detected_standalone_urls.append(url)

    has_standalone = len(detected_standalone_urls) > 0

    return {
        "has_standalone_website": has_standalone,
        "standalone_urls": detected_standalone_urls,
        "all_urls_checked": all_candidate_urls,
        "business_name": business_name,
        "location": location,
    }
