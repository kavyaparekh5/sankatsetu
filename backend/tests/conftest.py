import os
import pytest

# Set DATABASE_URL to a test database before any app modules are imported
os.environ["DATABASE_URL"] = "sqlite:///./test_disaster.db"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Report, Resource

# Create a test engine pointing to the test database
test_engine = create_engine(
    "sqlite:///./test_disaster.db", connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure the test database is clean before running tests, and cleaned up after."""
    # Delete test DB if it exists
    if os.path.exists("./test_disaster.db"):
        try:
            os.remove("./test_disaster.db")
        except Exception:
            pass

    # Create all tables on the test database
    Base.metadata.create_all(bind=test_engine)

    yield

    # Clean up after the test session finishes
    from app.database import engine as prod_engine
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    prod_engine.dispose()
    if os.path.exists("./test_disaster.db"):
        try:
            os.remove("./test_disaster.db")
        except Exception:
            pass


@pytest.fixture
def db():
    """Provides a transactional database session for a test.

    Rolls back any changes made during the test, ensuring test isolation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    """Provides a TestClient with overridden get_db dependency pointing to the test database session."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
