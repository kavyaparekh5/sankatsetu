"""
Pydantic schemas (API contract layer).

`Literal` types give us free 422 validation on source/category/resource
type without needing DB-level enums.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceType = Literal["twitter", "news", "citizen_app"]
CategoryType = Literal[
    "flood", "medical", "rescue", "fire", "infrastructure", "uncategorized"
]
ResourceType = Literal["ambulance", "ndrf_team", "shelter", "fire_unit", "hospital", "police_station"]
CredibilityLabel = Literal["Verified", "Likely", "Unverified"]


# ---------------------------------------------------------------------------
# Report schemas
# ---------------------------------------------------------------------------

class ReportCreate(BaseModel):
    text: str = Field(..., min_length=3, description="Raw report text")
    source: SourceType
    location_name: str
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class ReportOut(BaseModel):
    id: int
    text: str
    source: SourceType
    category: CategoryType
    location_name: str
    lat: float
    lng: float
    credibility_score: int
    credibility_label: CredibilityLabel
    verified_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Resource schemas
# ---------------------------------------------------------------------------

class ResourceOut(BaseModel):
    id: int
    name: str
    type: ResourceType
    lat: float
    lng: float
    is_available: bool

    class Config:
        from_attributes = True


class ResourceWithDistance(ResourceOut):
    distance_km: float


# ---------------------------------------------------------------------------
# Authentication schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4)
    role: Optional[str] = "citizen"


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

