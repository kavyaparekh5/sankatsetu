"""
Database configuration.

Uses SQLite by default so the project runs with zero external setup.
Swap SQLALCHEMY_DATABASE_URL for a Postgres URL later without touching
any other file (models/services/routes only talk to the ORM session).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///./disaster.db"
)

# check_same_thread=False is required for SQLite when used with FastAPI's
# threaded request handling. It has no effect on other database backends.
connect_args = (
    {"check_same_thread": False}
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
