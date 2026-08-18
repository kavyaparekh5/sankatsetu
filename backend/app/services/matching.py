"""
Geo distance + resource matching service.

Uses the Haversine formula (great-circle distance on a sphere) rather
than a routing API - no external calls, no API key, good enough
accuracy for "which resource is closest" at city scale.
"""

import math
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Resource

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def find_nearest_resources(
    db: Session,
    lat: float,
    lng: float,
    limit: int = 3,
    only_available: bool = True,
    resource_type: Optional[str] = None,
) -> list[tuple[Resource, float]]:
    """Return up to `limit` (Resource, distance_km) tuples, closest first."""
    query = db.query(Resource)
    if only_available:
        query = query.filter(Resource.is_available.is_(True))
    if resource_type:
        query = query.filter(Resource.type == resource_type)

    candidates = query.all()

    scored = [
        (resource, haversine_km(lat, lng, resource.lat, resource.lng))
        for resource in candidates
    ]
    scored.sort(key=lambda pair: pair[1])

    return scored[:limit]
