"""
ORM models.

Categories, sources and resource types are kept as plain strings (not
SQLAlchemy Enum columns) on purpose - it makes SQLite migrations and
seed-data editing trivial during a hackathon, while validation of the
*allowed* values still happens at the API boundary via Pydantic/Literal
in schemas.py.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)

    # twitter | news | citizen_app
    source = Column(String, nullable=False, index=True)

    # flood | medical | rescue | fire | infrastructure | uncategorized
    category = Column(String, nullable=False, index=True, default="uncategorized")

    location_name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    credibility_score = Column(Integer, nullable=False, default=0)
    verified_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    # ambulance | ndrf_team | shelter | fire_unit
    type = Column(String, nullable=False, index=True)

    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    is_available = Column(Boolean, nullable=False, default=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="citizen")  # authority | citizen

