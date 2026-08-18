import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


# ==============================================================================
# CRYPTOGRAPHY HELPERS
# ==============================================================================

def hash_password(password: str) -> str:
    """Hash password securely using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its PBKDF2 hash safely."""
    try:
        salt, key_hex = hashed.split("$")
        check_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return secrets.compare_digest(check_key.hex(), key_hex)
    except Exception:
        return False


# ==============================================================================
# ROUTE HANDLERS
# ==============================================================================

@router.post("/signup", response_model=UserOut, status_code=201)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user (defaulting to citizen role)."""
    # Check if user already exists
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Validate role to only allow citizen or authority
    role = payload.role if payload.role in ["authority", "citizen"] else "citizen"

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Login and return a mock token containing the role and username."""
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    return Token(
        access_token=f"mock-jwt-token-{user.username}-{user.role}",
        token_type="bearer",
        role=user.role,
        username=user.username
    )
