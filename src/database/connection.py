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
    engine = get_engine()

    # Use raw psycopg2 connection — handles $$ function bodies and multi-statement SQL correctly
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            # Check if main table already exists
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'cli_mappings')"
            )
            exists = cur.fetchone()[0]

            if not exists:
                logger.info("Running initial migration...")

                # Step 1: Enable extensions
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    logger.info("  pgvector extension enabled.")
                except Exception as e:
                    logger.warning(f"  pgvector extension warning: {e}")
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                except Exception as e:
                    logger.warning(f"  pg_trgm extension warning: {e}")

                # Step 2: Create tables
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cli_mappings (
                        id                  SERIAL PRIMARY KEY,
                        tag                 VARCHAR(20) NOT NULL,
                        functional_intent   TEXT NOT NULL,
                        cisco_ios           TEXT DEFAULT '',
                        cisco_iosxe         TEXT DEFAULT '',
                        cisco_nxos          TEXT DEFAULT '',
                        extreme_exos        TEXT DEFAULT '',
                        extreme_voss        TEXT DEFAULT '',
                        extreme_slxos       TEXT DEFAULT '',
                        negation_cisco      TEXT DEFAULT '',
                        negation_en         TEXT DEFAULT '',
                        notes               TEXT DEFAULT '',
                        source_ref          VARCHAR(255) DEFAULT '',
                        page_ref            VARCHAR(100) DEFAULT '',
                        embedding           vector(384),
                        confidence          FLOAT DEFAULT 1.0,
                        is_verified         BOOLEAN DEFAULT FALSE,
                        created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS extraction_runs (
                        id              SERIAL PRIMARY KEY,
                        source_type     VARCHAR(20) NOT NULL,
                        source_name     VARCHAR(255) NOT NULL,
                        rows_added      INTEGER DEFAULT 0,
                        rows_updated    INTEGER DEFAULT 0,
                        started_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        completed_at    TIMESTAMP WITH TIME ZONE,
                        status          VARCHAR(20) DEFAULT 'running',
                        error_message   TEXT
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS query_log (
                        id                  SERIAL PRIMARY KEY,
                        query_text          TEXT NOT NULL,
                        tag_filter          VARCHAR(20),
                        os_filter           VARCHAR(30),
                        results_count       INTEGER,
                        top_similarity      FLOAT,
                        response_time_ms    INTEGER,
                        created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS crawler_urls (
                        id              SERIAL PRIMARY KEY,
                        url             TEXT UNIQUE NOT NULL,
                        os_target       VARCHAR(30),
                        last_crawled    TIMESTAMP WITH TIME ZONE,
                        status          VARCHAR(20) DEFAULT 'pending',
                        rows_produced   INTEGER DEFAULT 0,
                        http_status     INTEGER,
                        error_message   TEXT
                    );
                """)

                # Step 3: Basic indexes (NOT ivfflat — requires data, created after seed)
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_cli_tag ON cli_mappings(tag);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_cli_intent_trgm ON cli_mappings USING gin(functional_intent gin_trgm_ops);")
                except Exception as e:
                    logger.warning(f"  Index warning: {e}")

                raw_conn.commit()
                logger.info("Migration complete — tables created.")
            else:
                logger.info("Schema already exists, skipping migration.")
    except Exception as e:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()


def init_db():
    """Full initialization: run migrations + verify connection."""
    try:
        run_migrations()
        logger.info(f"Database initialized: {DATABASE_URL.split('@')[-1]}")
        return True
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise
