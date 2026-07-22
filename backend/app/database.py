from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def prepare_connection(database_url: str) -> tuple[str, dict]:
    """
    Returns (cleaned_url, connect_args) for create_async_engine(). Pulled
    out as its own pure function specifically so it can be unit tested
    without touching global module state (engine creation, sys.modules,
    etc.) — see tests/test_database_pooler_fix.py.

    Two real, well-documented incompatibilities between SQLAlchemy's
    asyncpg dialect and how every major managed Postgres provider (Neon,
    Supabase, AWS RDS) formats its default connection string:

    1. SQLAlchemy forwards URL query params as raw Python kwargs straight
       to asyncpg.connect(). `sslmode` and `channel_binding` are
       libpq/psql conventions, not part of asyncpg's own API, so this
       throws `TypeError: connect() got an unexpected keyword argument
       'sslmode'` — a 5+ year old, still-open SQLAlchemy issue that hits
       nearly everyone connecting to a managed Postgres provider this
       way. Fixed by stripping both from the URL and passing SSL via
       connect_args using the name asyncpg actually expects (`ssl`, not
       `sslmode`).
    2. asyncpg's prepared-statement cache breaks against PgBouncer in
       transaction-pooling mode (what Neon's, Supabase's, and most
       providers' "pooled connection" endpoint uses) with
       DuplicatePreparedStatementError — often not on the first
       connection, only under real traffic. Disabled unconditionally for
       any Postgres URL; this app doesn't lean on that optimization
       enough for the cost to matter.
    """
    if not database_url.startswith("postgresql"):
        return database_url, {}

    # The single most common mistake deploying this: pasting a managed
    # Postgres provider's connection string exactly as given, which is
    # always plain `postgresql://` with no driver specified. SQLAlchemy
    # then silently defaults to the sync psycopg2 driver — which isn't
    # installed, since this app is async-only — and startup fails with
    # `ModuleNotFoundError: No module named 'psycopg2'`. Rather than keep
    # asking a human to remember to type `+asyncpg` correctly every time
    # they paste a connection string, the code just fixes it.
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    parsed = urlparse(database_url)
    query = parse_qs(parsed.query)
    query.pop("sslmode", None)
    query.pop("channel_binding", None)
    cleaned_url = urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    connect_args = {
        "ssl": "require",
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
    return cleaned_url, connect_args


_database_url, _connect_args = prepare_connection(settings.DATABASE_URL)
engine = create_async_engine(_database_url, echo=False, connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
