from datetime import datetime, timedelta, timezone
import os
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

# Import helper functions
from helperFunction import generate_otp, send_otp_email

# --- ENFORCE MANDATORY SECRETS ---
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Fail fast if SECRET_KEY is not configured in production
    raise RuntimeError("CRITICAL: SECRET_KEY environment variable is not set!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Enforce SSL and Pool configuration
if DATABASE_URL and "6543" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )
elif DATABASE_URL and "postgresql" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if DATABASE_URL and "sqlite" in DATABASE_URL else {},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# --- DATABASE MODEL ---
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    failed_otp_attempts = Column(Integer, default=0)  # Counter to block brute-force attacks

    # Daily Request Limit Fields
    daily_request_limit = Column(Integer, default=50, nullable=False)  # Max requests per day
    requests_used_today = Column(Integer, default=0, nullable=False)
    last_request_reset_date = Column(Date, default=datetime.now(timezone.utc).date, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- STRICT VALIDATION SCHEMAS ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Password must be between 8 and 64 characters",
    )


class Token(BaseModel):
    access_token: str
    token_type: str


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class ResendOTPRequest(BaseModel):
    email: EmailStr


class RequestUsageResponse(BaseModel):
    email: str
    requests_used_today: int
    daily_request_limit: int
    requests_remaining: int


# --- SECURITY HELPERS ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    # Truncate to 72 bytes max for native bcrypt safety
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(UserDB).filter(UserDB.email == email).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_admin_user(current_user: UserDB = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for this action.",
        )
    return current_user


def verify_request_quota(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserDB:
    """
    Dependency that resets daily counters when a new day starts, checks request limits,
    and increments usage for protected routes.
    """
    today = datetime.now(timezone.utc).date()

    # 1. Automatic Midnight UTC Reset
    if current_user.last_request_reset_date is None or current_user.last_request_reset_date < today:
        current_user.requests_used_today = 0
        current_user.last_request_reset_date = today
        db.commit()

    # 2. Reject request if limit met
    if current_user.requests_used_today >= current_user.daily_request_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Daily request limit reached.",
                "requests_used": current_user.requests_used_today,
                "daily_limit": current_user.daily_request_limit,
                "resets_at": "Midnight UTC",
            },
        )

    # 3. Increment request count
    current_user.requests_used_today += 1
    db.commit()

    return current_user


# --- ENDPOINTS ---
@router.post("/signup", response_model=dict)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(UserDB).filter(UserDB.email == user.email).first()

    otp_code = generate_otp()
    code_expires = datetime.now(timezone.utc) + timedelta(minutes=10)

    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Email is already registered.")

        # Refresh credentials & code for existing unverified accounts
        existing_user.hashed_password = get_password_hash(user.password)
        existing_user.verification_code = otp_code
        existing_user.code_expires_at = code_expires
        existing_user.failed_otp_attempts = 0
        db.commit()

        send_otp_email(user.email, otp_code)
        return {"status": "success", "message": "Verification code sent to your email"}

    # Register new unverified user
    new_user = UserDB(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        is_verified=False,
        verification_code=otp_code,
        code_expires_at=code_expires,
        failed_otp_attempts=0,
    )
    db.add(new_user)
    db.commit()

    send_otp_email(user.email, otp_code)
    return {"status": "success", "message": "Verification code sent to your email"}


@router.post("/verify-otp", response_model=dict)
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification request")

    if user.is_verified:
        return {"status": "success", "message": "Account is already verified"}

    # 1. Enforce Max Attempt Threshold (Brute Force Defense)
    if user.failed_otp_attempts >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please request a new verification code.",
        )

    # 2. Check Expiration First
    if user.code_expires_at:
        expires_at = user.code_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=400, detail="Verification code expired. Please request a new one.")

    # 3. Validate Code
    if not user.verification_code or user.verification_code != payload.code.strip():
        user.failed_otp_attempts = (user.failed_otp_attempts or 0) + 1
        db.commit()
        remaining = 5 - user.failed_otp_attempts
        raise HTTPException(
            status_code=400,
            detail=f"Invalid code. {remaining} attempt(s) remaining.",
        )

    # Mark user as verified & clear OTP state
    user.is_verified = True
    user.verification_code = None
    user.code_expires_at = None
    user.failed_otp_attempts = 0
    db.commit()

    return {"status": "success", "message": "Account verified successfully"}


@router.post("/resend-otp", response_model=dict)
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if not user or user.is_verified:
        # Generic message to prevent user enumeration
        return {"status": "success", "message": "If the account exists and is unverified, a new code was sent."}

    otp_code = generate_otp()
    user.verification_code = otp_code
    user.code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    user.failed_otp_attempts = 0
    db.commit()

    send_otp_email(user.email, otp_code)
    return {"status": "success", "message": "If the account exists and is unverified, a new code was sent."}


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        otp_code = generate_otp()
        user.verification_code = otp_code
        user.code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        user.failed_otp_attempts = 0
        db.commit()
        send_otp_email(user.email, otp_code)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified. A new verification code has been sent to your email.",
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/usage", response_model=RequestUsageResponse)
def get_usage_status(current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    """Read-only check for user's remaining daily requests without consuming a quota count."""
    today = datetime.now(timezone.utc).date()
    if current_user.last_request_reset_date is None or current_user.last_request_reset_date < today:
        current_user.requests_used_today = 0
        current_user.last_request_reset_date = today
        db.commit()

    remaining = max(0, current_user.daily_request_limit - current_user.requests_used_today)
    return {
        "email": current_user.email,
        "requests_used_today": current_user.requests_used_today,
        "daily_request_limit": current_user.daily_request_limit,
        "requests_remaining": remaining,
    }