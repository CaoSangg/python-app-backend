from unittest.mock import Mock

import pytest

from tests.integration.database import (
    UnsafeTestDatabase,
    require_test_database_url,
    verify_test_connection,
)


TEST_URL = "postgresql+asyncpg://songs_test_runner:test@db_test:5432/songs_test_db"


def test_requires_test_url_even_if_application_url_is_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    with pytest.raises(UnsafeTestDatabase, match="Set TEST_DATABASE_URL"):
        require_test_database_url(None)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://postgres:secret@db:5432/songs_db",
        TEST_URL + "?host=db&database=songs_db",
        TEST_URL + "?options=-ccluster_name%3Dsong_management_integration",
        TEST_URL.replace("songs_test_runner:", "postgres:"),
        TEST_URL.replace(":5432", ":invalid"),
    ],
)
def test_rejects_unsafe_test_url_without_echoing_it(url):
    with pytest.raises(UnsafeTestDatabase) as error:
        require_test_database_url(url)
    assert url not in str(error.value)


def test_accepts_dedicated_test_url():
    assert require_test_database_url(TEST_URL).host == "db_test"


@pytest.mark.parametrize(
    "identity",
    [
        ("songs_db", "songs_test_runner", "song_management_integration"),
        ("songs_test_db", "postgres", "song_management_integration"),
        ("songs_test_db", "songs_test_runner", ""),
    ],
)
def test_rejects_connection_if_actual_identity_does_not_match(identity):
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = identity
    with pytest.raises(UnsafeTestDatabase, match="Connected PostgreSQL server"):
        verify_test_connection(connection, None)
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[0].startswith("SELECT ")
    cursor.close.assert_called_once()
    connection.rollback.assert_called_once()
