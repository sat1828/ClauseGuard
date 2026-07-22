import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import prepare_connection


def test_sqlite_url_untouched():
    url, args = prepare_connection("sqlite+aiosqlite:///./clauseguard.db")
    assert url == "sqlite+aiosqlite:///./clauseguard.db"
    assert args == {}


def test_postgres_url_strips_sslmode_and_channel_binding():
    """The actual bug: SQLAlchemy's asyncpg dialect forwards sslmode= and
    channel_binding= as raw Python kwargs to asyncpg.connect(), which
    doesn't recognize either name and throws TypeError. Both must be gone
    from the cleaned URL."""
    raw = "postgresql+asyncpg://user:pass@ep-something.neon.tech/neondb?sslmode=require&channel_binding=require"
    url, args = prepare_connection(raw)
    assert "sslmode" not in url
    assert "channel_binding" not in url


def test_postgres_url_gets_correct_ssl_connect_arg():
    """SSL still needs to be required — just passed the way asyncpg's own
    API actually expects it (`ssl`), not the libpq/psql name that breaks."""
    raw = "postgresql+asyncpg://user:pass@ep-something.neon.tech/neondb?sslmode=require&channel_binding=require"
    url, args = prepare_connection(raw)
    assert args["ssl"] == "require"


def test_postgres_url_disables_prepared_statement_cache():
    """Guards against DuplicatePreparedStatementError when connecting
    through a PgBouncer pooler (Neon's/Supabase's '-pooler' endpoints)."""
    raw = "postgresql+asyncpg://user:pass@ep-something-pooler.neon.tech/neondb?sslmode=require"
    url, args = prepare_connection(raw)
    assert args["statement_cache_size"] == 0
    assert args["prepared_statement_cache_size"] == 0


def test_non_pooled_postgres_url_still_gets_the_fix():
    """Applied unconditionally for any postgresql:// URL — simpler and
    harmless for a direct (non-pooled) connection too."""
    raw = "postgresql+asyncpg://user:pass@ep-direct.neon.tech/neondb?sslmode=require"
    url, args = prepare_connection(raw)
    assert args["statement_cache_size"] == 0


def test_postgres_url_preserves_other_query_params():
    """Only sslmode and channel_binding get stripped — anything else the
    user has in their connection string survives untouched."""
    raw = "postgresql+asyncpg://user:pass@host/db?sslmode=require&application_name=clauseguard"
    url, args = prepare_connection(raw)
    assert "application_name=clauseguard" in url


def test_postgres_url_without_ssl_params_is_still_handled():
    """A connection string with no sslmode/channel_binding at all (e.g. a
    local Postgres for testing) shouldn't error or behave differently."""
    raw = "postgresql+asyncpg://user:pass@localhost/db"
    url, args = prepare_connection(raw)
    assert url == raw
    assert args["ssl"] == "require"


def test_credentials_and_host_survive_the_cleanup():
    """Sanity check that we're not accidentally mangling the actually
    important parts of the URL while stripping query params."""
    raw = "postgresql+asyncpg://myuser:mypass@ep-host.neon.tech/mydb?sslmode=require"
    url, args = prepare_connection(raw)
    assert "myuser:mypass@ep-host.neon.tech" in url
    assert "/mydb" in url


def test_bare_postgresql_url_auto_upgraded_to_asyncpg():
    """The exact real-world mistake: pasting a Neon connection string
    exactly as given (plain postgresql://, no driver) used to silently
    fall through to the sync psycopg2 driver, which isn'"'"'t installed, and
    crash with ModuleNotFoundError at startup. This has actually happened
    in a real deployment. The code now fixes it instead of relying on a
    human to type +asyncpg correctly."""
    raw = "postgresql://neondb_owner:secret@ep-something-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    url, args = prepare_connection(raw)
    assert url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in url
    assert "channel_binding" not in url
    assert args["ssl"] == "require"


def test_already_correct_asyncpg_url_untouched_by_upgrade_logic():
    raw = "postgresql+asyncpg://user:pass@host/db?sslmode=require"
    url, args = prepare_connection(raw)
    assert url.count("+asyncpg") == 1  # not double-prefixed into +asyncpg+asyncpg


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
