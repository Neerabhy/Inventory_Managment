import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from sqlite3 import Connection as SQLite3Connection
from app.core.config import settings

# Initialize logging context for tracing analytical database performance
logger = logging.getLogger("app.core.database")

# Generate the asynchronous core engine instance
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    # WAL Mode requires single/controlled pool structures inside local thread environments
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Enforce foreign key constraints inside the SQLite storage engine
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()
        logger.info("SQLite database connection tuned with WAL engine parameters and foreign keys enabled.")

# Configure async operational factory instances
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Shared Declarative Base for Schema Objects
class Base(DeclarativeBase):
    pass