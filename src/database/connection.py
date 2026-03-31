"""Database engine, session factory, and migration runner."""
import logging
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from src.config import DATABASE_URL, BASE_DIR
from src.database.models import Base

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_session() -> Session:
    """Context manager for database sessions with auto-commit/rollback."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_migrations():
    """Apply the initial SQL migration if tables don't exist yet."""
    migration_file = BASE_DIR / "src" / "database" / "migrations" / "001_initial.sql"
    engine = get_engine()

    with engine.connect() as conn:
        # Check if main table already exists
        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'cli_mappings')"
        ))
        exists = result.scalar()

        if not exists:
            logger.info("Running initial migration...")
            sql = migration_file.read_text()
            # Execute statements one at a time (split on semicolons, skip empty)
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        logger.warning(f"Migration statement warning: {e}")
            conn.commit()
            logger.info("Migration complete.")
        else:
            logger.info("Schema already exists, skipping migration.")


def init_db():
    """Full initialization: run migrations + verify connection."""
    try:
        run_migrations()
        logger.info(f"Database initialized: {DATABASE_URL.split('@')[-1]}")
        return True
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise
