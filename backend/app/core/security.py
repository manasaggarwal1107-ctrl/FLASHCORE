import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from pathlib import Path
from pwdlib import PasswordHash


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

password_hasher = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "flashcore"


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters.")
    return secret


def get_access_token_lifetime() -> int:
    try:
        minutes = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30"))
    except ValueError as exc:
        raise RuntimeError("JWT_ACCESS_TOKEN_MINUTES must be an integer.") from exc

    if not 1 <= minutes <= 1440:
        raise RuntimeError("JWT access token lifetime must be between 1 and 1440 minutes.")

    return minutes


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(user_id: int, jti: uuid.UUID) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=get_access_token_lifetime())

    payload = {
        "sub": str(user_id),
        "jti": str(jti),
        "iat": now,
        "exp": expires_at,
        "iss": JWT_ISSUER,
    }

    token = jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        options={
            "require": ["sub", "jti", "iat", "exp", "iss"],
        },
    )
