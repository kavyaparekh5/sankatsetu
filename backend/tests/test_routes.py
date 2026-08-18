import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Report, Resource


# ==============================================================================
# 1. HEALTH CHECK ENDPOINT
# ==============================================================================

def test_health_check(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Disaster Intelligence API" in data["service"]


# ==============================================================================
# 2. REPORTS ENDPOINTS
# ==============================================================================

def test_create_report_success(client: TestClient, db: Session):
    # Ensure database is clean of reports
    db.query(Report).delete()
    db.commit()

    payload = {
        "text": "Big fire in a building, smoke rising fast",
        "source": "citizen_app",
        "location_name": "Maninagar, Ahmedabad",
        "lat": 22.9962,
        "lng": 72.6081,
    }
    response = client.post("/reports", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["text"] == payload["text"]
    assert data["source"] == "citizen_app"
    # Auto-classification should match "fire"
    assert data["category"] == "fire"
    assert data["location_name"] == payload["location_name"]
    assert data["lat"] == payload["lat"]
    assert data["lng"] == payload["lng"]
    # Base score for citizen_app = 35. No corroboration or verifications.
    assert data["credibility_score"] == 35
    assert data["credibility_label"] == "Unverified"
    assert data["verified_count"] == 0
    assert "created_at" in data

    # Verify database entry exists
    db_report = db.query(Report).filter(Report.id == data["id"]).first()
    assert db_report is not None
    assert db_report.category == "fire"


def test_create_report_validation_errors(client: TestClient):
    # 1. Text too short
    response = client.post(
        "/reports",
        json={
            "text": "Hi",
            "source": "citizen_app",
            "location_name": "Test",
            "lat": 22.0,
            "lng": 72.0,
        },
    )
    assert response.status_code == 422

    # 2. Invalid source type
    response = client.post(
        "/reports",
        json={
            "text": "Valid text length here",
            "source": "invalid_source",
            "location_name": "Test",
            "lat": 22.0,
            "lng": 72.0,
        },
    )
    assert response.status_code == 422

    # 3. Invalid latitude range
    response = client.post(
        "/reports",
        json={
            "text": "Valid text length here",
            "source": "citizen_app",
            "location_name": "Test",
            "lat": -100.0,
            "lng": 72.0,
        },
    )
    assert response.status_code == 422


def test_list_reports(client: TestClient, db: Session):
    db.query(Report).delete()
    db.commit()

    # Seed some specific reports
    r1 = Report(
        text="Flood near station",
        source="news",
        category="flood",
        location_name="Station",
        lat=22.99,
        lng=72.60,
        credibility_score=80,
    )
    r2 = Report(
        text="Fire at office",
        source="twitter",
        category="fire",
        location_name="Office",
        lat=22.95,
        lng=72.55,
        credibility_score=20,
    )
    db.add_all([r1, r2])
    db.commit()

    # 1. Get all reports
    response = client.get("/reports")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # 2. Filter by category
    response = client.get("/reports?category=flood")
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "flood"

    # 3. Filter by min_score
    response = client.get("/reports?min_score=50")
    data = response.json()
    assert len(data) == 1
    assert data[0]["credibility_score"] >= 50


def test_get_report_by_id(client: TestClient, db: Session):
    db.query(Report).delete()
    db.commit()

    report = Report(
        text="Some incident occurred",
        source="news",
        category="uncategorized",
        location_name="Unknown",
        lat=22.0,
        lng=72.0,
        credibility_score=50,
    )
    db.add(report)
    db.commit()

    # Success case
    response = client.get(f"/reports/{report.id}")
    assert response.status_code == 200
    assert response.json()["text"] == "Some incident occurred"

    # Not found case
    response = client.get("/reports/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"


def test_verify_report_endpoint(client: TestClient, db: Session):
    db.query(Report).delete()
    db.commit()

    report = Report(
        text="Power cut in the area",
        source="citizen_app",
        category="infrastructure",
        location_name="Bopal",
        lat=23.0325,
        lng=72.4568,
        credibility_score=35,  # Base citizen_app
        verified_count=0,
    )
    db.add(report)
    db.commit()

    # Post verification
    response = client.post(f"/reports/{report.id}/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["verified_count"] == 1
    # Score should increase: base 35 + 1 verification (+5) = 40. Label is now Likely.
    assert data["credibility_score"] == 40
    assert data["credibility_label"] == "Likely"

    # Post verification on non-existing ID
    response = client.post("/reports/99999/verify")
    assert response.status_code == 404


def test_suggested_resources_for_report(client: TestClient, db: Session):
    db.query(Report).delete()
    db.query(Resource).delete()
    db.commit()

    # Create report at (22.9962, 72.6081)
    report = Report(
        text="Emergency rescue needed, flooding worsens",
        source="citizen_app",
        category="rescue",
        location_name="Maninagar",
        lat=22.9962,
        lng=72.6081,
    )
    db.add(report)

    # Create resources
    res_close = Resource(
        name="Rescue Team Close", type="ndrf_team", lat=22.9965, lng=72.6080, is_available=True
    )
    res_far = Resource(
        name="Rescue Team Far", type="ndrf_team", lat=23.0728, lng=72.6534, is_available=True
    )
    res_unavailable = Resource(
        name="Close Unavailable Rescue Team", type="ndrf_team", lat=22.9964, lng=72.6082, is_available=False
    )
    db.add_all([res_close, res_far, res_unavailable])
    db.commit()

    response = client.get(f"/reports/{report.id}/suggested-resources")
    assert response.status_code == 200
    data = response.json()

    # Should only return available resources, sorted by distance
    assert len(data) == 2
    assert data[0]["name"] == "Rescue Team Close"
    assert data[1]["name"] == "Rescue Team Far"
    assert "distance_km" in data[0]

    # Non-existing report ID
    response = client.get("/reports/99999/suggested-resources")
    assert response.status_code == 404


# ==============================================================================
# 3. RESOURCES ENDPOINTS
# ==============================================================================

def test_list_resources(client: TestClient, db: Session):
    db.query(Resource).delete()
    db.commit()

    res = Resource(name="Ambulance A", type="ambulance", lat=22.0, lng=72.0)
    db.add(res)
    db.commit()

    response = client.get("/resources")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Ambulance A"


def test_nearby_resources_endpoint(client: TestClient, db: Session):
    db.query(Resource).delete()
    db.commit()

    res1 = Resource(name="Ambulance Close", type="ambulance", lat=22.9960, lng=72.6075, is_available=True)
    res2 = Resource(name="Ambulance Far", type="ambulance", lat=23.0300, lng=72.4550, is_available=True)
    db.add_all([res1, res2])
    db.commit()

    # Success case
    response = client.get("/resources/nearby?lat=22.9962&lng=72.6081")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Ambulance Close"

    # With parameters
    response = client.get("/resources/nearby?lat=22.9962&lng=72.6081&limit=1")
    assert len(response.json()) == 1

    # Validation check: missing lat/lng
    response = client.get("/resources/nearby?lat=22.9962")
    assert response.status_code == 422
