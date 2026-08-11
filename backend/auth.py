import os
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Boolean, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from passlib.context import CryptContext
import resend
from typing import Optional

# Import helper functions
from helperFunction import generate_otp, send_otp_email

# Initialize Resend API Key
resend.api_key = os.getenv("RESEND_API_KEY", "")

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-fallback-key-change-in-railway")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Get DATABASE_URL from Railway environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix legacy prefix if necessary
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure engine for Transaction Mode Pooler
if DATABASE_URL and "6543" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,  # Let Supabase Pooler manage connections
        pool_pre_ping=True
    )
else:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if DATABASE_URL and "sqlite" in DATABASE_URL else {}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# --- DATABASE MODEL WITH ADMIN & OTP SUPPORT ---
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    code_expires_at = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- SCHEMAS ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    code: str


class ResendOTPRequest(BaseModel):
    email: EmailStr


# --- AUTH HELPERS USING NATIVE BCRYPT ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    # Truncate to 72 bytes to match bcrypt limit
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
            detail="Admin privileges required for this action."
        )
    return current_user


# --- ENDPOINTS ---
@router.post("/signup", response_model=dict)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(UserDB).filter(UserDB.email == user.email).first()

    # Generate 6-digit OTP code with 10-minute expiry
    otp_code = generate_otp()
    code_expires = datetime.now(timezone.utc) + timedelta(minutes=10)

    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Update existing unverified user with new password & OTP
        existing_user.hashed_password = get_password_hash(user.password)
        existing_user.verification_code = otp_code
        existing_user.code_expires_at = code_expires
        db.commit()

        send_otp_email(user.email, otp_code)
        return {"status": "success", "message": "Verification code resent to your email"}

    # Create new unverified user
    hashed_pwd = get_password_hash(user.password)
    new_user = UserDB(
        email=user.email,
        hashed_password=hashed_pwd,
        is_verified=False,
        verification_code=otp_code,
        code_expires_at=code_expires
    )
    db.add(new_user)
    db.commit()

    send_otp_email(user.email, otp_code)
    return {"status": "success", "message": "Verification code sent to your email"}


@router.post("/verify-otp", response_model=dict)
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")

    if user.is_verified:
        return {"status": "success", "message": "Account is already verified"}

    if not user.verification_code or user.verification_code != payload.code.strip():
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Check code expiration
    if user.code_expires_at:
        expires_at = user.code_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    # Mark user as verified
    user.is_verified = True
    user.verification_code = None
    user.code_expires_at = None
    db.commit()

    return {"status": "success", "message": "Account verified successfully"}


@router.post("/resend-otp", response_model=dict)
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Account is already verified")

    otp_code = generate_otp()
    user.verification_code = otp_code
    user.code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    send_otp_email(user.email, otp_code)
    return {"status": "success", "message": "A new verification code has been sent"}


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Prevent login if email is not verified
    if not user.is_verified:
        # Send fresh OTP when unverified login attempt occurs
        otp_code = generate_otp()
        user.verification_code = otp_code
        user.code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        db.commit()
        send_otp_email(user.email, otp_code)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified. A new verification code has been sent to your email."
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}