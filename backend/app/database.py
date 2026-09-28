"""
Database connection setup.

Uses SQLite by default (a single file, zero setup - perfect for this
project's data size). Swap DATABASE_URL in .env to a Postgres URL later
if you deploy somewhere without persistent disk, and nothing else in the
codebase needs to change.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# Hosts (Render/Heroku/Neon) may hand out "postgres://", which SQLAlchemy 2 rejects.
DATABASE_URL = settings.database_url
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping: managed Postgres closes idle connections; this reconnects instead of erroring.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
