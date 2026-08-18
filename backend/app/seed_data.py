"""
Seed script: populates the database with realistic sample data so the API
and any frontend can be demoed without needing live Twitter/News access.

Run directly:
    python -m app.seed_data

Or it runs automatically on startup (see main.py) if the reports table
is empty.

Sample reports are clustered geographically/temporally around a few
Ahmedabad localities on purpose, so that the corroboration scoring in
services/scoring.py has real clusters to detect during a demo.
"""

from datetime import datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.models import Report, Resource
from app.services.classification import classify
from app.services.scoring import compute_credibility_score

now = datetime.utcnow()

# (text, source, location_name, lat, lng, minutes_ago)
SAMPLE_REPORTS = [
    (
        "Heavy flooding reported near Maninagar, water entering homes, "
        "several families trapped on rooftops and requesting rescue boats.",
        "citizen_app", "Maninagar, Ahmedabad", 22.9962, 72.6081, 10,
    ),
    (
        "Flood waters rising fast in Maninagar area, multiple streets "
        "submerged, vehicles stranded.",
        "twitter", "Maninagar, Ahmedabad", 22.9971, 72.6095, 25,
    ),
    (
        "Maninagar flooding worsens as heavy rainfall continues; local "
        "authorities say rescue boats have been requested urgently.",
        "news", "Maninagar, Ahmedabad", 22.9955, 72.6070, 40,
    ),
    (
        "People stranded on a rooftop near Maninagar railway station, "
        "urgently need rescue, water still rising.",
        "twitter", "Near Maninagar Station, Ahmedabad", 22.9940, 72.6100, 15,
    ),
    (
        "Fire broke out in a garment factory in the Naroda industrial "
        "estate, thick smoke visible from a distance.",
        "news", "Naroda Industrial Estate, Ahmedabad", 23.0728, 72.6534, 55,
    ),
    (
        "Fire department responding to industrial fire in Naroda, one "
        "worker reported injured and taken for treatment.",
        "news", "Naroda Industrial Estate, Ahmedabad", 23.0715, 72.6520, 30,
    ),
    (
        "Building collapse reported in Vatva, residents believed trapped "
        "under debris, neighbours attempting to clear rubble by hand.",
        "citizen_app", "Vatva, Ahmedabad", 22.9647, 72.6488, 20,
    ),
    (
        "Ambulance requested urgently for an injured person pulled from "
        "the Vatva building collapse site, condition critical.",
        "citizen_app", "Vatva, Ahmedabad", 22.9650, 72.6495, 5,
    ),
    (
        "Medical camp reports a rise in waterborne illness cases in "
        "Isanpur following days of flooding, hospital beds filling up.",
        "citizen_app", "Isanpur, Ahmedabad", 22.9750, 72.6100, 120,
    ),
    (
        "Storm has knocked down electricity poles in Bopal, residents "
        "report a power outage across several streets since this morning.",
        "citizen_app", "Bopal, Ahmedabad", 23.0325, 72.4568, 180,
    ),
]

SAMPLE_RESOURCES = [
    ("Ambulance Unit 1", "ambulance", 22.9950, 72.6070, True),
    ("NDRF Rescue Team Alpha", "ndrf_team", 22.9660, 72.6470, True),
    ("City Fire Station 3", "fire_unit", 23.0700, 72.6500, True),
    ("Isanpur School Emergency Shelter", "shelter", 22.9740, 72.6120, True),
    ("Ambulance Unit 2", "ambulance", 23.0300, 72.4550, False),
    ("NDRF Rescue Team Bravo", "ndrf_team", 23.0300, 72.6800, True),
    ("Ahmedabad General Hospital", "hospital", 22.9975, 72.6015, True),
    ("Apex Trauma Center", "hospital", 23.0650, 72.6420, True),
    ("Maninagar Police Station", "police_station", 22.9930, 72.6090, True),
    ("Naroda Police Division", "police_station", 23.0780, 72.6590, True),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if db.query(Report).count() > 0 or db.query(Resource).count() > 0:
            print("Database already has data — skipping seed.")
            return

        # Reports are inserted oldest-first so that corroboration scoring
        # (which looks at reports created before/around the same time)
        # builds up naturally, the same way it would in a live system.
        ordered = sorted(SAMPLE_REPORTS, key=lambda r: r[5], reverse=True)

        for text, source, location_name, lat, lng, minutes_ago in ordered:
            category = classify(text)
            created_at = now - timedelta(minutes=minutes_ago)

            score = compute_credibility_score(
                db,
                category=category,
                source=source,
                lat=lat,
                lng=lng,
                created_at=created_at,
                verified_count=0,
                exclude_id=None,
            )

            db.add(
                Report(
                    text=text,
                    source=source,
                    category=category,
                    location_name=location_name,
                    lat=lat,
                    lng=lng,
                    credibility_score=score,
                    verified_count=0,
                    created_at=created_at,
                )
            )
            db.commit()

        for name, rtype, lat, lng, is_available in SAMPLE_RESOURCES:
            db.add(
                Resource(
                    name=name,
                    type=rtype,
                    lat=lat,
                    lng=lng,
                    is_available=is_available,
                )
            )
        db.commit()

        print(
            f"Seeded {len(SAMPLE_REPORTS)} reports and "
            f"{len(SAMPLE_RESOURCES)} resources."
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
