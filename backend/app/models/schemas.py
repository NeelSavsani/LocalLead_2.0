from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


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
    maps_url: Optional[str] = None
    has_maps_site: bool = False
    has_web_site: bool = False
    verification_status: str = "No Standalone Website Found"
    call_status: str = "Pending Call"
    pitch_angle: str = "Digital storefront & direct customer booking"
    date_identified: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    )


class ScanCandidateEvent(BaseModel):
    job_id: str
    candidate_name: str
    category: Optional[str] = None
    status: str  # "EVALUATING" | "DISQUALIFIED_MAPS" | "DISQUALIFIED_SEARCH" | "QUALIFIED" | "COMPLETED"
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
    status: str = "RUNNING"  # "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"
    latest_log: Optional[str] = None
    is_completed: bool = False


class StartScanResponse(BaseModel):
    job_id: str
    message: str
    target_limit: int
    categories: List[str]
