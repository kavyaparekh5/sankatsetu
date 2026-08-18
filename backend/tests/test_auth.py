import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from app.routes.auth import hash_password, verify_password


# ==============================================================================
# 1. CRYPTOGRAPHY TESTS
# ==============================================================================

def test_password_hashing():
    raw_password = "SecurePassword123"
    hashed = hash_password(raw_password)
    
    assert hashed != raw_password
    assert "$" in hashed
    
    # Verify split format
    salt, key_hex = hashed.split("$")
    assert len(salt) == 32  # hex of 16 bytes
    assert len(key_hex) == 64  # hex of 32 bytes (SHA-256 output)


def test_password_verification():
    raw_password = "MySecretPassword"
    hashed = hash_password(raw_password)
    
    # Correct verification
    assert verify_password(raw_password, hashed) is True
    
    # Incorrect verification
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password("", hashed) is False
    
    # Invalid format verification handles exception safely
    assert verify_password(raw_password, "invalid_hash_string_without_dollar") is False


# ==============================================================================
# 2. ENDPOINT INTEGRATION TESTS
# ==============================================================================

def test_signup_success(client: TestClient, db: Session):
    db.query(User).delete()
    db.commit()

    payload = {
        "username": "test_officer",
        "password": "officerpassword",
        "role": "authority"
    }
    
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["id"] is not None
    assert data["username"] == "test_officer"
    assert data["role"] == "authority"
    assert "password" not in data  # Should not expose password
    
    # Confirm database storage
    db_user = db.query(User).filter(User.username == "test_officer").first()
    assert db_user is not None
    assert db_user.role == "authority"
    assert verify_password("officerpassword", db_user.password_hash) is True


def test_signup_duplicate_username(client: TestClient, db: Session):
    db.query(User).delete()
    db.commit()

    # Pre-create user
    db.add(User(
        username="existing_user",
        password_hash=hash_password("somepassword"),
        role="citizen"
    ))
    db.commit()

    # Attempt to sign up with same username
    payload = {
        "username": "existing_user",
        "password": "newpassword",
        "role": "citizen"
    }
    
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already registered"


def test_login_success(client: TestClient, db: Session):
    db.query(User).delete()
    db.commit()

    # Pre-create authority user
    db.add(User(
        username="admin_officer",
        password_hash=hash_password("adminpass123"),
        role="authority"
    ))
    db.commit()

    payload = {
        "username": "admin_officer",
        "password": "adminpass123"
    }
    
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "authority"
    assert data["username"] == "admin_officer"


def test_login_invalid_credentials(client: TestClient, db: Session):
    db.query(User).delete()
    db.commit()

    # Pre-create user
    db.add(User(
        username="john_doe",
        password_hash=hash_password("correct_password"),
        role="citizen"
    ))
    db.commit()

    # 1. Wrong password
    response = client.post("/auth/login", json={
        "username": "john_doe",
        "password": "wrong_password"
    })
    assert response.status_code == 401
    
    # 2. Non-existent username
    response = client.post("/auth/login", json={
        "username": "non_existent",
        "password": "any_password"
    })
    assert response.status_code == 401
