import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

# Load backend environment configuration
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    value = int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Prefer a managed database URL when supplied by the deployment platform.
DATABASE_URL_ENV = os.getenv("DATABASE_URL")

if DATABASE_URL_ENV:
    database_url = make_url(DATABASE_URL_ENV)

    # Explicitly use Psycopg 3.
    if database_url.drivername in ("postgresql", "postgres"):
        database_url = database_url.set(
            drivername="postgresql+psycopg"
        )

    # Require encrypted connections to the managed database.
    query = dict(database_url.query)
    query.setdefault("sslmode", "require")
    database_url = database_url.set(query=query)
else:
    # Preserve the existing local PostgreSQL configuration.
    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "flashcore_db"),
    )

POOL_SIZE = _int_env("DB_POOL_SIZE", 5, minimum=1)
MAX_OVERFLOW = _int_env("DB_MAX_OVERFLOW", 10, minimum=0)
POOL_TIMEOUT = _int_env("DB_POOL_TIMEOUT", 30, minimum=1)
POOL_RECYCLE = _int_env("DB_POOL_RECYCLE", 1800, minimum=0)
POOL_PRE_PING = _bool_env("DB_POOL_PRE_PING", True)
USE_NULL_POOL = _bool_env("DB_USE_NULL_POOL", False)

if USE_NULL_POOL:
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        pool_pre_ping=POOL_PRE_PING,
        echo=False,
    )
else:
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT,
        pool_recycle=POOL_RECYCLE,
        pool_pre_ping=POOL_PRE_PING,
        echo=False,
    )

DATABASE_URL = database_url

# Database session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Base class for database models
class Base(DeclarativeBase):
    pass


# Dependency for FastAPI database sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
