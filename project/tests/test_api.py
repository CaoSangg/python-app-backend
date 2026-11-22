import logging
from unittest.mock import MagicMock, Mock

import pytest
from asyncpg import InterfaceError, InvalidPasswordError
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app import db
from app.main import app
from app.models import Song


@pytest.fixture
def database(monkeypatch):
    engine = MagicMock(spec=AsyncEngine)
    connection = MagicMock(spec=AsyncConnection)
    engine.connect.return_value.__aenter__.return_value = connection

    session = MagicMock(spec=AsyncSession)
    session.__aenter__.return_value = session
    session_factory = Mock(return_value=session)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/test")
    monkeypatch.setattr(db, "create_async_engine", Mock(return_value=engine))
    monkeypatch.setattr(db, "async_sessionmaker", Mock(return_value=session_factory))
    return engine, connection, session


@pytest.fixture
def client(database):
    with TestClient(app) as test_client:
        yield test_client
    database[0].dispose.assert_awaited_once()


@pytest.fixture
def song():
    return Song(id=7, name="Midnight Fit", artist="Mogwai", year=2021)


def test_create_song(client, database, song):
    session = database[2]

    def assign_id():
        session.add.call_args.args[0].id = song.id

    session.commit.side_effect = assign_id
    response = client.post("/songs", json={"name": " Midnight Fit ", "artist": "Mogwai", "year": "2021"})

    assert response.status_code == 201
    assert response.json() == song.model_dump()
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


def test_list_songs(client, database, song):
    session = database[2]
    result = Mock()
    result.all.side_effect = [[], [song]]
    session.exec.return_value = result

    empty_response = client.get("/songs")
    response = client.get("/songs")

    assert empty_response.status_code == 200
    assert empty_response.json() == []
    assert response.status_code == 200
    assert response.json() == [song.model_dump()]
    session.commit.assert_not_awaited()


def test_get_song(client, database, song):
    session = database[2]
    session.get.return_value = song

    response = client.get("/songs/7")

    assert response.status_code == 200
    assert response.json() == song.model_dump()
    session.get.assert_awaited_once_with(Song, 7)


@pytest.mark.parametrize("year_field", [{"year": 2022}, {}, {"year": None}])
def test_replace_song(client, database, song, year_field):
    session = database[2]
    session.get.return_value = song
    payload = {"name": "Ritchie Sacramento", "artist": "Mogwai", **year_field}

    response = client.put("/songs/7", json=payload)

    assert response.status_code == 200
    assert response.json() == {"id": 7, **payload, "year": year_field.get("year")}
    assert song.name == payload["name"]
    assert song.year == year_field.get("year")
    session.commit.assert_awaited_once()


def test_delete_song(client, database, song):
    session = database[2]
    session.get.return_value = song

    response = client.delete("/songs/7")

    assert response.status_code == 204
    assert response.content == b""
    session.delete.assert_awaited_once_with(song)
    session.commit.assert_awaited_once()


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_missing_song(client, database, method):
    session = database[2]
    session.get.return_value = None
    body = {"json": {"name": "Song", "artist": "Artist"}} if method == "PUT" else {}

    response = client.request(method, "/songs/99", **body)

    assert response.status_code == 404
    assert response.json() == {"detail": "Song not found"}
    session.commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"artist": "Artist"}, "name"),
        ({"name": "Song"}, "artist"),
        ({"name": " ", "artist": "Artist"}, "name"),
        ({"name": "Song\x00", "artist": "Artist"}, "name"),
        ({"name": "Song", "artist": 1}, "artist"),
        ({"name": "Song", "artist": "Artist", "year": "unknown"}, "year"),
        ({"name": "Song", "artist": "Artist", "year": True}, "year"),
        ({"name": "Song", "artist": "Artist", "year": 2021.5}, "year"),
        ({"name": "Song", "artist": "Artist", "year": 2**31}, "year"),
    ],
)
@pytest.mark.parametrize(("method", "url"), [("POST", "/songs"), ("PUT", "/songs/7")])
def test_invalid_payload(client, database, method, url, payload, field):
    response = client.request(method, url, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
    database[2].add.assert_not_called()
    database[2].get.assert_not_awaited()
    database[2].commit.assert_not_awaited()


@pytest.mark.parametrize("song_id", ["invalid", "0", "-1", str(2**31)])
def test_invalid_song_id(client, database, song_id):
    response = client.get(f"/songs/{song_id}")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "song_id"]
    database[2].get.assert_not_awaited()


def test_db_write_failure(client, database, caplog):
    session = database[2]
    session.commit.side_effect = OperationalError("INSERT", {"credential": "secret"}, OSError())

    response = client.post("/songs", json={"name": "Song", "artist": "Artist"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Database operation failed"}
    session.__aexit__.assert_awaited_once()
    assert "Database operation failed (OperationalError)" in caplog.text
    assert "secret" not in caplog.text


def test_liveness_never_connects(client, database):
    engine, connection, _ = database

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    engine.connect.assert_not_called()
    connection.execute.assert_not_awaited()


def test_readiness_queries_postgresql(client, database):
    engine, connection, _ = database

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    connection.execute.assert_awaited_once()
    assert str(connection.execute.await_args.args[0]) == "SELECT 1"
    engine.connect.return_value.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("error_type", [OSError, InvalidPasswordError, InterfaceError, TimeoutError])
def test_readiness_returns_sanitized_503(client, database, caplog, error_type):
    engine, _, _ = database
    secret = "postgresql+asyncpg://username:secret@internal/test"
    engine.connect.return_value.__aenter__.side_effect = error_type(secret)

    with caplog.at_level(logging.WARNING):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert f"Database readiness check failed ({error_type.__name__})" in caplog.text
    assert secret not in caplog.text


def test_readiness_when_query_fails(client, database):
    engine, connection, _ = database
    connection.execute.side_effect = OperationalError("SELECT 1", {}, OSError())

    assert client.get("/health/ready").status_code == 503
    engine.connect.return_value.__aexit__.assert_awaited_once()


def test_api_starts_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert client.get("/songs").status_code == 503


def test_ping_and_swagger(client):
    assert client.get("/ping").json() == {"ping": "pong!"}
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "Swagger UI" in docs.text

    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]["/songs"]) == {"get", "post"}
    assert set(schema["paths"]["/songs/{song_id}"]) == {"get", "put", "delete"}
    assert {"201", "422", "500", "503"} <= set(schema["paths"]["/songs"]["post"]["responses"])
    assert "503" in schema["paths"]["/health/ready"]["get"]["responses"]
