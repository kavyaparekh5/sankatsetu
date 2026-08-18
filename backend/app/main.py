from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, SessionLocal, engine
from app.models import Report, User
from app.routes import reports, resources, auth
from app.routes.auth import hash_password
from app.seed_data import seed

app = FastAPI(
    title="Disaster Intelligence API",
    description=(
        "Backend for the Multi-Source Disaster Intelligence and Response "
        "Support System hackathon MVP: report ingestion, keyword-based "
        "classification, credibility scoring, and nearest-resource matching."
    ),
    version="1.0.0",
)

# CORS: wide open for the hackathon demo so a React frontend on any port
# (e.g. Vite's default localhost:5173) can call this API directly.
# Tighten `allow_origins` before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports.router)
app.include_router(resources.router)
app.include_router(auth.router)

# Serve the static frontend dashboard at /ui
app.mount("/ui", StaticFiles(directory="../frontend", html=True), name="ui")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

    # Auto-seed demo data on first run so the API is immediately
    # demoable without a manual extra step.
    db = SessionLocal()
    try:
        # Seed default admin user if not present
        if db.query(User).filter(User.username == "admin").count() == 0:
            db.add(User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="authority"
            ))
            db.commit()

        if db.query(Report).count() == 0:
            seed()
    finally:
        db.close()


@app.get("/", tags=["health"])
def health_check():
    return {
        "status": "ok",
        "service": "Disaster Intelligence API",
        "docs": "/docs",
    }
