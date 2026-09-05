import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

# Unicode patterns for stripping emojis and special font icons (Material, Private Use Area)
EMOJI_AND_ICON_PATTERN = re.compile(
    "["
    "\U00010000-\U0010ffff"  # Supplemental symbols, pictographs, emoji
    "\u200d\u200c\u2060-\u206f"
    "\u2600-\u27bf"          # Miscellaneous symbols & dingbats
    "\u2300-\u23ff"          # Miscellaneous technical
    "\u2b50"                 # Star
    "\ufe00-\ufe0f"          # Variation selectors
    "\ue000-\uf8ff"          # Private use area (Google Maps / Material icon font codepoints)
    "]+",
    flags=re.UNICODE
)

NON_COMMERCIAL_PATTERNS = [
    r"\bvilla(s)?\b",
    r"\bapartment(s)?\b",
    r"\bsociety\b",
    r"\bbunglow(s)?\b",
    r"\bbungalow(s)?\b",
    r"\bflat(s)?\b",
    r"\bresidency\b",
    r"\bresidence\b",
    r"\btenement(s)?\b",
    r"\brow\s*house(s)?\b",
    r"\bchawl\b",
    r"\bnivas\b",
    r"\bniwas\b",
    r"\bhousing\s*society\b",
    r"\bresidential\b",
]

HOME_COMMERCIAL_EXCEPTIONS = re.compile(
    r"\bhome\s+(decor|furniture|appliances|care|foods|bakers|kitchen|interiors|textiles|furnishing|solutions|automation|clinic|made|service|baking)\b",
    flags=re.I
)


def clean_business_name(name: str) -> str:
    """
    Cleans raw business names:
    - Strips emojis and private-use/special icon characters.
    - Strips bullet points, stars, and decorative symbols.
    - Strips trailing pipe/location noise e.g. '| Ahmedabad'.
    - Strips leading and trailing punctuation noise.
    """
    if not name:
        return ""
    cleaned = EMOJI_AND_ICON_PATTERN.sub("", name)
    cleaned = re.sub(r'[\u2018\u2019\u201c\u201d•·★*]+', ' ', cleaned)
    cleaned = re.sub(r'\s*\|\s*.*$', '', cleaned)
    cleaned = re.sub(r'^[\s\-_|,:;/.]+', '', cleaned)
    cleaned = re.sub(r'[\s\-_|,:;/.]+$', '', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


import unicodedata

LISTICLE_KEYWORDS = [
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


def is_listicle_title(name: str) -> bool:
    if not name or len(name.strip()) < 2:
        return True
    norm = "".join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c)).lower()
    norm = f" {norm.strip()} "
    for kw in LISTICLE_KEYWORDS:
        if kw in norm:
            return True
    return False


def is_commercial_business(name: str) -> bool:
    """
    Filters out non-commercial entities and listicle/blog titles:
    Rejects names containing 'Villa', 'Apartment', 'Society', 'Bunglow',
    'Home' (unless commercial home decor/care/foods), 'Flat', 'Residency', etc.
    Strictly discards listicles and aggregator headlines.
    """
    if not name or len(name.strip()) < 2:
        return False
    lower = name.lower()
    if is_listicle_title(lower):
        return False
    for pattern in NON_COMMERCIAL_PATTERNS:
        if re.search(pattern, lower):
            return False
    if re.search(r"\bhome\b", lower):
        if not HOME_COMMERCIAL_EXCEPTIONS.search(lower) and "nursing home" not in lower:
            return False
    return True


class ScanRequest(BaseModel):
    location: str = Field(
        ...,
        description="Target city, neighborhood, or area (e.g. 'Surat, Gujarat')",
        examples=["Surat, Gujarat"]
    )
    categories: List[str] = Field(
        default_factory=list,
        description="List of target business categories (e.g. ['Cafe', 'Garage', 'Restaurant'])"
    )
    # Backward compatibility for single category parameter
    category: Optional[str] = Field(
        default=None,
        description="Optional single category for legacy compatibility"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of verified leads to collect before halting"
    )
    use_mock: bool = Field(
        default=False,
        description="Whether to use offline testing data instead of live internet search"
    )
    require_phone: bool = Field(
        default=True,
        description="Discard candidates whose Google Maps place drawer has no callable phone number"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_categories(cls, values):
        if isinstance(values, dict):
            cats = values.get("categories")
            single_cat = values.get("category")
            if not cats and single_cat:
                values["categories"] = [single_cat]
            elif not cats and not single_cat:
                raise ValueError("At least one category must be specified.")
            elif cats and isinstance(cats, list) and len(cats) == 0:
                if single_cat:
                    values["categories"] = [single_cat]
                else:
                    raise ValueError("At least one category must be specified in categories.")
        return values


class LeadRecord(BaseModel):
    id: str
    name: str
    category: str
    phone: Optional[str] = "N/A"
    address: str
    area: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    maps_url: Optional[str] = None
    has_maps_site: bool = False
    has_web_site: bool = False
    verification_status: str = "No Standalone Website Found"
    call_status: str = "Pending Call"
    pitch_angle: str = "Digital storefront & direct customer booking"
    date_identified: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = clean_business_name(v)
        if not is_commercial_business(cleaned):
            raise ValueError(f"Discarded non-commercial or residential entity: '{v}'")
        if len(cleaned) < 2:
            raise ValueError(f"Business name is too short: '{v}'")
        return cleaned

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v or len(v.strip()) < 3:
            raise ValueError(f"Address format too vague or invalid: '{v}'")
        return v.strip()


class ScanCandidateEvent(BaseModel):
    job_id: str
    candidate_name: str
    category: Optional[str] = None
    status: str  # "EVALUATING" | "DISQUALIFIED_MAPS" | "DISQUALIFIED_SEARCH" | "QUALIFIED" | "COMPLETED" | "STOPPED"
    reason: str
    qualified_count: int
    target_limit: int
    lead: Optional[LeadRecord] = None


class ScanProgress(BaseModel):
    job_id: str
    processed_count: int = 0
    qualified_count: int = 0
    target_limit: int = 20
    current_business: Optional[str] = None
    status: str = "RUNNING"  # "PENDING" | "RUNNING" | "COMPLETED" | "STOPPED" | "FAILED"
    latest_log: Optional[str] = None
    is_completed: bool = False


class StartScanResponse(BaseModel):
    job_id: str
    message: str
    target_limit: int
    categories: List[str]
