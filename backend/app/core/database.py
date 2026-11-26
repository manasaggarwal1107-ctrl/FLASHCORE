import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

# Load backend environment configuration
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

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

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
        echo=False,
    )
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

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
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

