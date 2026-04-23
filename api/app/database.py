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
    # TCP keepalive to prevent Cloud SQL proxy from dropping idle connections
    connect_args.update({
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    })
    pool_kwargs = {
        "poolclass": QueuePool,
        "pool_size": 3,           # max persistent connections per instance
        "max_overflow": 2,        # allow 2 extra temporary connections
        "pool_timeout": 30,       # wait 30s for a connection before erroring
        # Cloud SQL kills idle TCP at ~5 min. Recycling at exactly 300 races
        # the kill (the connection can die between pre_ping and the real
        # query). 240 keeps us comfortably under the kill window.
        "pool_recycle": 240,
        "pool_pre_ping": True,    # test connections before use (handles Cloud SQL restarts)
        # LIFO so the most-recently-used connection is reused — older idle
        # connections get a chance to age out and be recycled rather than
        # being kept perpetually warm just below the kill threshold.
        "pool_use_lifo": True,
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
