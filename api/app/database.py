import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool

from .config import settings

logger = logging.getLogger(__name__)

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# PostgreSQL: use small pool with recycling to avoid exhausting Cloud SQL slots.
# Cloud Run can have multiple instances, each with its own pool.
pool_kwargs = {}
if not settings.DATABASE_URL.startswith("sqlite"):
    # TCP-level keepalives so the OS detects dead Cloud SQL sockets faster
    # than psycopg2's defaults. Without these, a connection killed at the
    # network layer can sit in the pool unnoticed until a query mid-flight
    # returns "PGRES_TUPLES_OK and no message from the libpq" — observed
    # 2026-05-05 causing 503s to Gupshup. pool_pre_ping catches dead-on-
    # checkout; keepalives catch dead-mid-query.
    connect_args.update({
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    })
    # Pool sizing math (Hetzner self-hosted PostgreSQL):
    # - Local PostgreSQL max_connections = 200 (tuned in docker-compose).
    # - Gunicorn runs 4 workers (GUNICORN_WORKERS env, default 4).
    # - Each worker: 10 persistent + 10 overflow = 20 max connections.
    # - 4 workers × 20 = 80 max, well within 200 limit.
    # - Reserve ~20 slots for cron jobs, backups, manual psql, pg_stat.
    pool_kwargs = {
        "poolclass": QueuePool,
        "pool_size": 10,
        "max_overflow": 10,
        "pool_timeout": 30,       # wait 30s for a connection before erroring
        "pool_recycle": 1800,     # recycle idle connections every 30 min
        "pool_pre_ping": True,    # test connections before use
        "pool_use_lifo": True,    # reuse most-recent connection first
    }

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, **pool_kwargs)

# Dispose connections that encounter database errors (stale psycopg2 state)
@event.listens_for(engine, "handle_error")
def _handle_db_error(context):
    if context.connection is not None and not context.is_disconnect:
        logger.warning("DB error (invalidating connection): %s", context.original_exception)
        try:
            context.connection.invalidate()
        except Exception:
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
