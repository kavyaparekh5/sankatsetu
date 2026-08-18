# Disaster Intelligence API (Backend)

FastAPI backend for the **Multi-Source Disaster Intelligence and Response
Support System** hackathon MVP.

It ingests disaster reports (from citizens, social media, or news),
auto-classifies them, scores their credibility, and matches them to the
nearest available emergency resources — all with zero external
dependencies (no ML model, no live API keys, SQLite by default), so it
runs anywhere in under a minute.

## Features

- **Keyword-based classification** — assigns each report a category
  (`flood`, `medical`, `rescue`, `fire`, `infrastructure`, `uncategorized`).
- **Credibility scoring (0–100)** — combines source trust, corroboration
  from other nearby/recent reports of the same category, and citizen
  verifications into a `Verified` / `Likely` / `Unverified` label.
- **Nearest-resource matching** — Haversine-distance based matching of
  incidents to the closest available ambulances, NDRF teams, shelters,
  and fire units.
- **Seeded demo data** — 10 realistic sample reports (with a deliberate
  flood cluster near Maninagar to demonstrate corroboration scoring) and
  6 sample resources, loaded automatically on first run.

## Tech stack

Python · FastAPI · SQLAlchemy · SQLite · Pydantic

## Quick start (easiest way to run it)

**Option A — one command, if you have Python 3.10+ installed:**

```bash
# Mac/Linux
./start.sh

# Windows — just double-click start.bat, or run it from Command Prompt
start.bat
```

This creates the virtual environment, installs dependencies, and starts
the server, all in one step. Safe to run again later — it skips
anything already done. Open **http://127.0.0.1:8000/docs** once it says
"Application startup complete."

If you get a "permission denied" running `./start.sh` on Mac/Linux, run
`chmod +x start.sh` once, then try again.

**Option B — one command, if you have Docker installed (no Python needed at all):**

```bash
docker compose up
```

Then open **http://127.0.0.1:8000/docs**. Press `Ctrl+C` to stop.

**Option C — manual step-by-step** (see [Setup](#setup) below) if you
want full control over each step.

## Project structure

```text
backend/
├── app/
│   ├── main.py                # FastAPI app, CORS, startup/auto-seed
│   ├── database.py            # SQLAlchemy engine/session
│   ├── models.py              # Report, Resource ORM models
│   ├── schemas.py              # Pydantic request/response models
│   ├── seed_data.py            # Demo data seed script
│   ├── services/
│   │   ├── classification.py  # Keyword-based category classifier
│   │   ├── scoring.py          # Credibility scoring engine
│   │   └── matching.py         # Haversine distance + resource matching
│   └── routes/
│       ├── reports.py
│       └── resources.py
├── requirements.txt
└── README.md
```

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Seed the database manually
#    This also happens automatically on first app startup if empty.
python -m app.seed_data

# 4. Run the API
uvicorn app.main:app --reload
```

The API will be live at **http://127.0.0.1:8000**, with interactive docs
at **http://127.0.0.1:8000/docs**.

A React (or any) frontend running on a different port (e.g. Vite's
default `http://localhost:5173`) can call it directly — CORS is fully
open for the demo.

## Database

SQLite file `disaster.db` is created automatically in the project root
on first run — no external database server needed. To reset all data,
stop the server and delete `disaster.db`, then restart (it will
re-seed).

To point at Postgres instead, set an environment variable before
starting the app:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/disaster_db"
```

## API Endpoints

| Method | Path                                    | Description                                        |
|--------|------------------------------------------|-----------------------------------------------------|
| POST   | `/reports`                               | Submit a new report (auto-classified & scored)     |
| GET    | `/reports`                               | List reports (`?category=`, `?min_score=`)         |
| GET    | `/reports/{id}`                          | Get a single report                                |
| POST   | `/reports/{id}/verify`                   | Increment verification count, recompute score      |
| GET    | `/reports/{id}/suggested-resources`      | Nearest 3 available resources for that report      |
| GET    | `/resources`                             | List all resources                                 |
| GET    | `/resources/nearby?lat=&lng=`            | Nearest resources to any point                     |

### Example: submit a report

```bash
curl -X POST http://127.0.0.1:8000/reports \
  -H "Content-Type: application/json" \
  -d '{
        "text": "Flooding reported near Maninagar, people trapped, need rescue boats",
        "source": "citizen_app",
        "location_name": "Maninagar, Ahmedabad",
        "lat": 22.9962,
        "lng": 72.6081
      }'
```

### Example: verify a report

```bash
curl -X POST http://127.0.0.1:8000/reports/1/verify
```

### Example: find nearest resources to a point

```bash
curl "http://127.0.0.1:8000/resources/nearby?lat=22.996&lng=72.608&limit=3"
```

## How credibility scoring works

Each report starts from a **base score by source trust**
(news > citizen_app > twitter), then gains points for:

- **Corroboration** — other reports of the *same category*, within
  ~2km and ~2 hours, up to +30 (capped at 3 corroborating reports ×
  10 pts).
- **Citizen verification** — +5 per verification via
  `POST /reports/{id}/verify`, capped at +20 (4 verifications).

The final 0–100 score maps to a label:

- **70–100** → `Verified`
- **40–69**  → `Likely`
- **0–39**   → `Unverified`

This keeps the scoring fully explainable — an officer can see exactly
why a report scored what it did — rather than relying on an opaque
model.

## Notes

- This is a hackathon MVP: classification and scoring are intentionally
  simple, deterministic, and dependency-free so the demo is reliable.
  They're structured so a real ML/NLP model could later replace
  `services/classification.py` without touching the API layer.
- All sample data is clearly synthetic/demo data for demonstration
  purposes only and does not represent real emergencies.
