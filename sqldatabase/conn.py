import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config.sqlconfig import sqlsettings as settings
from config.pgconfig import pgsettings
from loguru import logger




sync_url = URL.create(
    "mysql+pymysql",
    username=settings.DB_USERNAME,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
)
logger.success(f"connection to database: {sync_url}")


async_url = URL.create(
    "mysql+aiomysql",
    username=settings.DB_USERNAME,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
)
    


engine = create_engine(sync_url, echo=True, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

async_engine = create_async_engine(
    async_url, 
    pool_pre_ping=True, 
    echo=True,
    pool_recycle=3600,  
    pool_size=5,
    max_overflow=10
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False  
)

class Base(DeclarativeBase):
    pass


# ============================================================================
# PostgreSQL (Neon) Async Connection for Vector Similarity Search
# ============================================================================

pg_async_url = URL.create(
    "postgresql+asyncpg",
    username=pgsettings.PGUSER,
    password=pgsettings.PGPASSWORD,
    host=pgsettings.PGHOST,
    port=int(pgsettings.PGPORT),
    database=pgsettings.PGDATABASE,
    query={"ssl": "require"}  # Neon requires SSL
)

pg_async_engine = create_async_engine(
    pg_async_url,
    pool_size=3,
    max_overflow=5,
    pool_recycle=3600
)

pg_async_session = async_sessionmaker(
    pg_async_engine,
    expire_on_commit=False
)

logger.success(f"PostgreSQL connection configured: {pgsettings.PGHOST}")
