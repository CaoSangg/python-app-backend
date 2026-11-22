from sqlalchemy import event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool


TEST_DATABASE = "songs_test_db"
TEST_ROLE = "songs_test_runner"
TEST_CLUSTER = "song_management_integration"


class UnsafeTestDatabase(RuntimeError):
    """Integration tests require a dedicated PostgreSQL target."""


def require_test_database_url(value: str | URL | None) -> URL:
    if not value:
        raise UnsafeTestDatabase("Set TEST_DATABASE_URL to the dedicated integration test database")

    try:
        url = make_url(value)
    except (ArgumentError, ValueError):
        raise UnsafeTestDatabase("Invalid TEST_DATABASE_URL") from None

    if (
        url.drivername != "postgresql+asyncpg"
        or url.database != TEST_DATABASE
        or url.username != TEST_ROLE
        or not url.host
        or not url.password
        or url.query
    ):
        raise UnsafeTestDatabase("TEST_DATABASE_URL must target the dedicated test database and role without URL options")
    return url


def verify_test_connection(connection, _connection_record) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT current_database(), current_user, current_setting('cluster_name')")
        identity = cursor.fetchone()
    finally:
        cursor.close()
        connection.rollback()

    if identity != (TEST_DATABASE, TEST_ROLE, TEST_CLUSTER):
        raise UnsafeTestDatabase("Connected PostgreSQL server is not the dedicated integration test database")


def create_test_engine(database_url: str | URL, **options) -> AsyncEngine:
    engine = create_async_engine(require_test_database_url(database_url), poolclass=NullPool, **options)
    # Check each actual connection before requests or fixtures can execute write SQL.
    event.listen(engine.sync_engine, "connect", verify_test_connection)
    return engine
