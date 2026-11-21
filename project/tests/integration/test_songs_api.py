"""
Integration Tests – Song Management API
Chạy với PostgreSQL thật (service 'db' trong docker-compose).
Không dùng mock – test toàn bộ luồng HTTP → FastAPI → SQLModel → PostgreSQL.
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import Song

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:Dev2024@db:5432/songs_db")


# =============================================================
# Database Fixtures
# =============================================================

@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_test_db():
    """Tạo bảng cơ sở dữ liệu một lần cho toàn bộ session."""
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await engine.dispose()
    yield
    cleanup_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with cleanup_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await cleanup_engine.dispose()


@pytest_asyncio.fixture
async def client():
    """HTTP client riêng cho từng test với lifespan context trong cùng event loop."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            yield ac


@pytest_asyncio.fixture(autouse=True)
async def clean_songs_table():
    """Xóa dữ liệu bảng song trước mỗi test bằng NullPool engine."""
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with AsyncSession(engine) as session:
        await session.exec(text("DELETE FROM song"))
        await session.commit()
    await engine.dispose()
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
async def test_liveness(client):
    """GET /health/live trả về ok."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness(client):
    """GET /health/ready kiểm tra kết nối DB thật."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    """POST /songs tạo bài hát mới thành công (HTTP 201)."""
    payload = {"name": "Noi Nay Co Anh", "artist": "Son Tung MTP", "year": 2017}
    response = await client.post("/songs", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Noi Nay Co Anh"
    assert data["artist"] == "Son Tung MTP"
    assert data["year"] == 2017
    assert "id" in data
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_create_song_without_year(client):
    """POST /songs không có year (optional field) vẫn thành công (HTTP 201)."""
    payload = {"name": "Lac Troi", "artist": "Son Tung MTP"}
    response = await client.post("/songs", json=payload)

    assert response.status_code == 201
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

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


# =============================================================
# Test: CRUD Full Flow (Integration)
# =============================================================

@pytest.mark.asyncio
async def test_crud_full_flow(client):
    """Tạo bài hát -> Get by ID -> Update -> Delete."""
    payload = {"name": "Chay Ngay Di", "artist": "Son Tung MTP", "year": 2016}
    create_resp = await client.post("/songs", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    song_id = created["id"]

    # GET by ID
    get_resp = await client.get(f"/songs/{song_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Chay Ngay Di"

    # UPDATE (PUT)
    update_resp = await client.put(f"/songs/{song_id}", json={"name": "Chay Ngay Di Remix", "artist": "Son Tung MTP", "year": 2018})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Chay Ngay Di Remix"

    # DELETE
    del_resp = await client.delete(f"/songs/{song_id}")
    assert del_resp.status_code == 204

    # GET lại -> 404
    get_again = await client.get(f"/songs/{song_id}")
    assert get_again.status_code == 404
