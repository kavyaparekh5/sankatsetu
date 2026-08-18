from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Resource
from app.schemas import ResourceOut, ResourceWithDistance
from app.services.matching import find_nearest_resources

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=list[ResourceOut])
def list_resources(db: Session = Depends(get_db)):
    return db.query(Resource).all()


@router.get("/nearby", response_model=list[ResourceWithDistance])
def nearby_resources(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    limit: int = Query(default=5, ge=1, le=50),
    only_available: bool = Query(default=True),
    resource_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Nearest resources to any arbitrary point (e.g. an incident location)."""
    nearest = find_nearest_resources(
        db,
        lat,
        lng,
        limit=limit,
        only_available=only_available,
        resource_type=resource_type,
    )

    return [
        ResourceWithDistance(
            id=resource.id,
            name=resource.name,
            type=resource.type,
            lat=resource.lat,
            lng=resource.lng,
            is_available=resource.is_available,
            distance_km=round(distance, 2),
        )
        for resource, distance in nearest
    ]
