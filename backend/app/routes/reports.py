from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Report
from app.schemas import ReportCreate, ReportOut, ResourceWithDistance
from app.services.classification import classify
from app.services.matching import find_nearest_resources
from app.services.scoring import compute_credibility_score, label_for_score

router = APIRouter(prefix="/reports", tags=["reports"])


def _to_report_out(report: Report) -> ReportOut:
    """Attach the human-readable credibility label on the way out."""
    return ReportOut(
        id=report.id,
        text=report.text,
        source=report.source,
        category=report.category,
        location_name=report.location_name,
        lat=report.lat,
        lng=report.lng,
        credibility_score=report.credibility_score,
        credibility_label=label_for_score(report.credibility_score),
        verified_count=report.verified_count,
        created_at=report.created_at,
    )


@router.post("", response_model=ReportOut, status_code=201)
def create_report(payload: ReportCreate, db: Session = Depends(get_db)):
    """Ingest a new report: auto-classify it and compute its initial score."""
    category = classify(payload.text)
    created_at = datetime.utcnow()

    score = compute_credibility_score(
        db,
        category=category,
        source=payload.source,
        lat=payload.lat,
        lng=payload.lng,
        created_at=created_at,
        verified_count=0,
        exclude_id=None,
    )

    report = Report(
        text=payload.text,
        source=payload.source,
        category=category,
        location_name=payload.location_name,
        lat=payload.lat,
        lng=payload.lng,
        credibility_score=score,
        verified_count=0,
        created_at=created_at,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return _to_report_out(report)


@router.get("", response_model=list[ReportOut])
def list_reports(
    category: Optional[str] = Query(default=None),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    db: Session = Depends(get_db),
):
    """List reports, newest first, with optional category/min_score filters."""
    query = db.query(Report)

    if category:
        query = query.filter(Report.category == category)
    if min_score is not None:
        query = query.filter(Report.credibility_score >= min_score)

    reports = query.order_by(Report.created_at.desc()).all()
    return [_to_report_out(r) for r in reports]


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_report_out(report)


@router.post("/{report_id}/verify", response_model=ReportOut)
def verify_report(report_id: int, db: Session = Depends(get_db)):
    """Increment a report's citizen-verification count and recompute its score."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.verified_count += 1

    report.credibility_score = compute_credibility_score(
        db,
        category=report.category,
        source=report.source,
        lat=report.lat,
        lng=report.lng,
        created_at=report.created_at,
        verified_count=report.verified_count,
        exclude_id=report.id,
    )

    db.commit()
    db.refresh(report)

    return _to_report_out(report)


@router.get("/{report_id}/suggested-resources", response_model=list[ResourceWithDistance])
def suggested_resources(report_id: int, limit: int = 3, db: Session = Depends(get_db)):
    """Nearest available resources to this report's location."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    nearest = find_nearest_resources(db, report.lat, report.lng, limit=limit)

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
