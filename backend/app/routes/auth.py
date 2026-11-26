import re
import uuid
from datetime import datetime, timezone
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    decode_access_token,
)
from app.models.auth import AuthSession, User


bearer_scheme = HTTPBearer(auto_error=False)


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class SignupRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    status: str
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserResponse


def issue_session(db: Session, user: User) -> AuthResponse:
    jti = uuid.uuid4()
    token, expires_at = create_access_token(user.id, jti)

    db.add(
        AuthSession(
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
        )
    )

    db.commit()
    db.refresh(user)

    return AuthResponse(
        access_token=token,
        expires_at=expires_at,
        user=user,
    )


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(User).where(func.lower(User.email) == payload.email)
    )

    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="analyst",
        status="active",
    )

    try:
        db.add(user)
        db.flush()
        return issue_session(db, user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        ) from exc


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(
        select(User).where(func.lower(User.email) == payload.email)
    )

    if (
        user is None
        or not verify_password(payload.password, user.password_hash)
        or user.status != "active"
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return issue_session(db, user)


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=204)
def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    try:
        payload = decode_access_token(credentials.credentials)
        jti = uuid.UUID(payload["jti"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid authentication credentials.")

    session = db.get(AuthSession, jti)

    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=401, detail="Invalid authentication session.")

    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return Response(status_code=204)
