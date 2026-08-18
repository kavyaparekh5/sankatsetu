"""
Credibility scoring service.

This is the core "intelligence" feature of the system: turning a raw,
unverified report into a 0-100 trust score a response officer can act on.

The score is built from three signals, all cheap to compute locally
(no external API calls, so it always works offline/at a hackathon venue):

1. Source trust        - a news article is inherently more vetted than
                          a single social media post.
2. Corroboration        - other independent reports of the SAME category,
                          reported NEAR the same place, AROUND the same
                          time, are strong evidence something real is
                          happening there.
3. Citizen verification - people on the ground marking a report as
                          confirmed ("I can see this too").

The score is intentionally simple and explainable rather than a black
box - an officer should be able to understand *why* a report scored
what it did.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Report
from app.services.matching import haversine_km

# --- Tunable constants -----------------------------------------------------

SOURCE_BASE_SCORE = {
    "news": 50,
    "citizen_app": 35,
    "twitter": 20,
}

CORROBORATION_RADIUS_KM = 2.0
CORROBORATION_WINDOW_HOURS = 2

POINTS_PER_CORROBORATING_REPORT = 10
MAX_CORROBORATION_REPORTS_COUNTED = 3  # caps corroboration bonus at +30

POINTS_PER_VERIFICATION = 5
MAX_VERIFICATIONS_COUNTED = 4  # caps verification bonus at +20

LABEL_THRESHOLDS = (
    (70, "Verified"),
    (40, "Likely"),
    (0, "Unverified"),
)


def label_for_score(score: int) -> str:
    """Map a numeric 0-100 credibility score to a human-readable label."""
    for threshold, label in LABEL_THRESHOLDS:
        if score >= threshold:
            return label
    return "Unverified"


def count_corroborating_reports(
    db: Session,
    category: str,
    lat: float,
    lng: float,
    around_time,
    exclude_id: int | None = None,
) -> int:
    """Count OTHER reports of the same category, within ~2km and ~2h.

    `around_time` is the timestamp corroboration is measured relative to
    (the report's own created_at) - this keeps the score stable/reproducible
    rather than drifting every time someone recomputes it later.
    """
    window_start = around_time - timedelta(hours=CORROBORATION_WINDOW_HOURS)
    window_end = around_time + timedelta(hours=CORROBORATION_WINDOW_HOURS)

    query = db.query(Report).filter(
        Report.category == category,
        Report.created_at >= window_start,
        Report.created_at <= window_end,
    )
    if exclude_id is not None:
        query = query.filter(Report.id != exclude_id)

    candidates = query.all()

    return sum(
        1
        for r in candidates
        if haversine_km(lat, lng, r.lat, r.lng) <= CORROBORATION_RADIUS_KM
    )


def compute_credibility_score(
    db: Session,
    *,
    category: str,
    source: str,
    lat: float,
    lng: float,
    created_at,
    verified_count: int,
    exclude_id: int | None = None,
) -> int:
    """Compute a fresh 0-100 credibility score for a report.

    Safe to call both at creation time (exclude_id=None, since the report
    isn't in the DB yet) and at re-scoring time e.g. after a new
    verification (exclude_id=<this report's id>, so it doesn't
    corroborate itself).
    """
    base = SOURCE_BASE_SCORE.get(source, 20)

    corroborating = count_corroborating_reports(
        db, category, lat, lng, created_at, exclude_id=exclude_id
    )
    corroboration_bonus = (
        min(corroborating, MAX_CORROBORATION_REPORTS_COUNTED)
        * POINTS_PER_CORROBORATING_REPORT
    )

    verification_bonus = (
        min(verified_count, MAX_VERIFICATIONS_COUNTED) * POINTS_PER_VERIFICATION
    )

    total = base + corroboration_bonus + verification_bonus
    return max(0, min(100, total))
