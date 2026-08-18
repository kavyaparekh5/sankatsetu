from datetime import datetime, timedelta
import pytest
from sqlalchemy.orm import Session

from app.models import Report, Resource
from app.services.classification import classify
from app.services.matching import find_nearest_resources, haversine_km
from app.services.scoring import (
    compute_credibility_score,
    count_corroborating_reports,
    label_for_score,
)


# ==============================================================================
# 1. CLASSIFICATION SERVICE TESTS
# ==============================================================================

def test_classify_simple_matches():
    # Test direct keyword matching
    assert classify("We have a severe flood in the area") == "flood"
    assert classify("The building caught fire and there is smoke") == "fire"
    assert classify("An injured citizen needs an ambulance") == "medical"
    assert classify("People are trapped on the roof and need rescue") == "rescue"
    assert classify("The storm caused a bridge collapse and road damage") == "infrastructure"


def test_classify_case_insensitivity():
    # Test case insensitivity
    assert classify("FLOODING REPORTED") == "flood"
    assert classify("smOkE and FiRe") == "fire"


def test_classify_tie_breaking():
    # If there is a tie, the category defined first in CATEGORY_KEYWORDS wins.
    # Order in classification.py: flood, fire, medical, rescue, infrastructure.
    # "flood" (from "flood") vs "fire" (from "fire") -> tie of 1 point each -> "flood" wins.
    assert classify("flood fire") == "flood"
    
    # "fire" (from "smoke") vs "medical" (from "injured") -> tie of 1 point -> "fire" wins.
    assert classify("smoke injured") == "fire"


def test_classify_fallback():
    # Test fallback to "uncategorized"
    assert classify("Normal day, nothing unusual happening here.") == "uncategorized"
    assert classify("") == "uncategorized"


# ==============================================================================
# 2. MATCHING SERVICE TESTS
# ==============================================================================

def test_haversine_distance():
    # Test distance between same point is 0
    dist_zero = haversine_km(22.9962, 72.6081, 22.9962, 72.6081)
    assert dist_zero == 0.0

    # Test distance calculation between two known points in Ahmedabad:
    # Maninagar (22.9962, 72.6081) to Naroda (23.0728, 72.6534)
    # The approximate distance is around 9.6 km.
    dist_ahmedabad = haversine_km(22.9962, 72.6081, 23.0728, 72.6534)
    assert 9.0 < dist_ahmedabad < 10.5


def test_find_nearest_resources(db: Session):
    # Clear any existing resources from database to ensure isolated test
    db.query(Resource).delete()
    db.commit()

    # Add test resources:
    # Reference point: Lat: 22.9962, Lng: 72.6081 (Maninagar)
    res_close = Resource(
        name="Close Ambulance",
        type="ambulance",
        lat=22.9960,
        lng=72.6075,
        is_available=True,
    )
    res_far = Resource(
        name="Far Ambulance",
        type="ambulance",
        lat=23.0300,
        lng=72.4550,
        is_available=True,
    )
    res_unavailable = Resource(
        name="Close Unavailable Rescue",
        type="ndrf_team",
        lat=22.9961,
        lng=72.6078,
        is_available=False,
    )
    res_fire = Resource(
        name="Close Fire Unit",
        type="fire_unit",
        lat=22.9963,
        lng=72.6085,
        is_available=True,
    )

    db.add_all([res_close, res_far, res_unavailable, res_fire])
    db.commit()

    # Query nearest resources:
    # 1. By default, only available resources are returned
    nearest = find_nearest_resources(db, lat=22.9962, lng=72.6081, limit=5)
    assert len(nearest) == 3
    # Check sorting order: close ambulance and fire unit are very close, far ambulance is far
    assert nearest[0][0].name in ["Close Ambulance", "Close Fire Unit"]
    assert nearest[1][0].name in ["Close Ambulance", "Close Fire Unit"]
    assert nearest[2][0].name == "Far Ambulance"

    # 2. Filter by type
    nearest_ambulance = find_nearest_resources(
        db, lat=22.9962, lng=72.6081, resource_type="ambulance", limit=5
    )
    assert len(nearest_ambulance) == 2
    assert all(r[0].type == "ambulance" for r in nearest_ambulance)

    # 3. Filter with only_available=False
    all_nearest = find_nearest_resources(
        db, lat=22.9962, lng=72.6081, only_available=False, limit=5
    )
    assert len(all_nearest) == 4
    # The unavailable team should be in the list
    assert any(r[0].name == "Close Unavailable Rescue" for r in all_nearest)

    # 4. Limit parameter
    limited = find_nearest_resources(db, lat=22.9962, lng=72.6081, limit=1)
    assert len(limited) == 1


# ==============================================================================
# 3. SCORING SERVICE TESTS
# ==============================================================================

def test_label_for_score():
    assert label_for_score(100) == "Verified"
    assert label_for_score(70) == "Verified"
    assert label_for_score(69) == "Likely"
    assert label_for_score(40) == "Likely"
    assert label_for_score(39) == "Unverified"
    assert label_for_score(0) == "Unverified"


def test_count_corroborating_reports(db: Session):
    db.query(Report).delete()
    db.commit()

    now = datetime.utcnow()

    # Reference point: Lat: 22.9962, Lng: 72.6081 (Maninagar), Category: flood
    # 1. Close and recent report (within 2km, within 2h) - Should corroborate
    r_corroborating = Report(
        text="Water level rising here too",
        source="twitter",
        category="flood",
        location_name="Maninagar East",
        lat=22.9970,
        lng=72.6090,
        created_at=now - timedelta(minutes=15),
    )

    # 2. Far report (> 2km) - Should NOT corroborate
    r_far = Report(
        text="Major flooding in Bopal",
        source="citizen_app",
        category="flood",
        location_name="Bopal",
        lat=23.0325,
        lng=72.4568,
        created_at=now - timedelta(minutes=10),
    )

    # 3. Old report (> 2h) - Should NOT corroborate
    r_old = Report(
        text="Flooding began near Maninagar",
        source="news",
        category="flood",
        location_name="Maninagar",
        lat=22.9962,
        lng=72.6081,
        created_at=now - timedelta(hours=3),
    )

    # 4. Different category - Should NOT corroborate
    r_diff_category = Report(
        text="A fire broke out in Maninagar",
        source="twitter",
        category="fire",
        location_name="Maninagar",
        lat=22.9962,
        lng=72.6081,
        created_at=now - timedelta(minutes=5),
    )

    db.add_all([r_corroborating, r_far, r_old, r_diff_category])
    db.commit()

    # Count corroborating reports for a new report at Maninagar
    count = count_corroborating_reports(
        db, category="flood", lat=22.9962, lng=72.6081, around_time=now
    )
    assert count == 1  # Only r_corroborating fits all conditions

    # Test exclusion: excluding r_corroborating's ID
    count_exclude = count_corroborating_reports(
        db,
        category="flood",
        lat=22.9962,
        lng=72.6081,
        around_time=now,
        exclude_id=r_corroborating.id,
    )
    assert count_exclude == 0


def test_compute_credibility_score(db: Session):
    db.query(Report).delete()
    db.commit()

    now = datetime.utcnow()

    # 1. Base score by source trust (no corroborations, no verifications)
    assert compute_credibility_score(db, category="flood", source="news", lat=22.9962, lng=72.6081, created_at=now, verified_count=0) == 50
    assert compute_credibility_score(db, category="flood", source="citizen_app", lat=22.9962, lng=72.6081, created_at=now, verified_count=0) == 35
    assert compute_credibility_score(db, category="flood", source="twitter", lat=22.9962, lng=72.6081, created_at=now, verified_count=0) == 20
    assert compute_credibility_score(db, category="flood", source="invalid_source", lat=22.9962, lng=72.6081, created_at=now, verified_count=0) == 20

    # 2. Add corroborating reports
    # Let's add 2 corroborating reports (category="flood", near, recent)
    r1 = Report(
        text="Corroboration 1",
        source="twitter",
        category="flood",
        location_name="Near",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
    )
    r2 = Report(
        text="Corroboration 2",
        source="twitter",
        category="flood",
        location_name="Near",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
    )
    db.add_all([r1, r2])
    db.commit()

    # Twitter base score = 20 + 2 corroborations (+20) = 40
    score_with_corrob = compute_credibility_score(
        db,
        category="flood",
        source="twitter",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
        verified_count=0,
    )
    assert score_with_corrob == 40

    # 3. Test corroboration bonus cap (+30 maximum, i.e. 3 reports count)
    r3 = Report(
        text="Corroboration 3",
        source="twitter",
        category="flood",
        location_name="Near",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
    )
    r4 = Report(
        text="Corroboration 4",
        source="twitter",
        category="flood",
        location_name="Near",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
    )
    db.add_all([r3, r4])
    db.commit()

    # Base = 20 + 4 corroborations (capped at 3 -> +30) = 50
    score_corrob_capped = compute_credibility_score(
        db,
        category="flood",
        source="twitter",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
        verified_count=0,
    )
    assert score_corrob_capped == 50

    # 4. Test verification bonus (+5 per verification, capped at +20 i.e. 4 verifications)
    # Base = 20, Corrob = 0, Verifications = 2 (+10) -> Total = 30
    score_verif = compute_credibility_score(
        db,
        category="fire",  # change category so no corroborations from flood reports
        source="twitter",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
        verified_count=2,
    )
    assert score_verif == 30

    # Base = 20, Corrob = 0, Verifications = 5 (capped at 4 -> +20) -> Total = 40
    score_verif_capped = compute_credibility_score(
        db,
        category="fire",
        source="twitter",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
        verified_count=5,
    )
    assert score_verif_capped == 40

    # 5. Test score capping at 100
    # News base = 50, Corrob = 4 (+30 capped), Verifications = 10 (+20 capped) -> 50 + 30 + 20 = 100
    score_max = compute_credibility_score(
        db,
        category="flood",
        source="news",
        lat=22.9962,
        lng=72.6081,
        created_at=now,
        verified_count=10,
    )
    assert score_max == 100
