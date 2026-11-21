"""
Integration Tests – Song Management API
Chạy với PostgreSQL thật (service 'db' trong docker-compose).
Không dùng mock – test toàn bộ luồng HTTP → FastAPI → SQLModel → PostgreSQL.
"""
import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel, text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.db import engine


# =============================================================
# Event Loop – phải là session-scoped để dùng chung với fixtures
# session-scoped khác (pytest-asyncio 0.21.x yêu cầu)
# =============================================================

@pytest.fixture(scope="session")
def event_loop():
    """Override event_loop thành session-scoped."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================
# Fixtures
# =============================================================

@pytest_asyncio.fixture(scope="session")
async def prepare_database():
    """Tạo bảng một lần cho cả session, xóa sau khi tất cả test xong."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture(scope="session")
async def client(prepare_database):
    """Dùng chung một HTTP client cho cả session (hiệu quả hơn)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def clean_songs_table(prepare_database):
    """Xóa toàn bộ dữ liệu bảng song trước mỗi test để độc lập."""
    async with AsyncSession(engine) as session:
        await session.execute(text("DELETE FROM song"))
        await session.commit()
    yield


# =============================================================
# Test: Healthcheck & Basic Connectivity
# =============================================================

@pytest.mark.asyncio
async def test_ping_returns_pong(client):
    """GET /ping không cần DB → luôn trả về pong."""
    response = await client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong!"}


@pytest.mark.asyncio
async def test_docs_accessible(client):
    """Swagger UI phải load được (HTTP 200)."""
    response = await client.get("/docs")
    assert response.status_code == 200


# =============================================================
# Test: GET /songs
# =============================================================

@pytest.mark.asyncio
async def test_get_songs_empty(client):
    """GET /songs trả về [] khi DB trống."""
    response = await client.get("/songs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_songs_returns_list(client):
    """GET /songs trả về list sau khi có dữ liệu."""
    await client.post("/songs", json={"name": "Song A", "artist": "Artist A", "year": 2020})
    await client.post("/songs", json={"name": "Song B", "artist": "Artist B", "year": 2021})

    response = await client.get("/songs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = [s["name"] for s in data]
    assert "Song A" in names
    assert "Song B" in names


# =============================================================
# Test: POST /songs
# =============================================================

@pytest.mark.asyncio
async def test_create_song_success(client):
    """POST /songs tạo bài hát mới thành công."""
    payload = {"name": "Noi Nay Co Anh", "artist": "Son Tung MTP", "year": 2017}
    response = await client.post("/songs", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Noi Nay Co Anh"
    assert data["artist"] == "Son Tung MTP"
    assert data["year"] == 2017
    assert "id" in data
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_create_song_without_year(client):
    """POST /songs không có year (optional field) vẫn thành công."""
    payload = {"name": "Lac Troi", "artist": "Son Tung MTP"}
    response = await client.post("/songs", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Lac Troi"
    assert data["year"] is None


@pytest.mark.asyncio
async def test_create_song_missing_required_field(client):
    """POST /songs thiếu 'artist' → 422 Unprocessable Entity."""
    payload = {"name": "No Artist Song"}
    response = await client.post("/songs", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_multiple_songs_have_unique_ids(client):
    """Mỗi bài hát tạo ra phải có id duy nhất (auto-increment)."""
    r1 = await client.post("/songs", json={"name": "Song 1", "artist": "A", "year": 2001})
    r2 = await client.post("/songs", json={"name": "Song 2", "artist": "B", "year": 2002})

    assert r1.json()["id"] != r2.json()["id"]


# =============================================================
# Test: CRUD Full Flow (Integration)
# =============================================================

@pytest.mark.asyncio
async def test_create_then_retrieve_song(client):
    """Tạo bài hát → GET /songs → xác nhận dữ liệu khớp."""
    payload = {"name": "Chay Ngay Di", "artist": "Son Tung MTP", "year": 2016}
    create_resp = await client.post("/songs", json=payload)
    assert create_resp.status_code == 200
    created = create_resp.json()

    list_resp = await client.get("/songs")
    assert list_resp.status_code == 200
    songs = list_resp.json()

    found = next((s for s in songs if s["id"] == created["id"]), None)
    assert found is not None
    assert found["name"] == "Chay Ngay Di"
    assert found["artist"] == "Son Tung MTP"
    assert found["year"] == 2016
