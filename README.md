# Song Management API

> **Đồ án DevOps – Phase 1** | FastAPI + PostgreSQL 16 + Docker

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100-green)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://postgresql.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## Giới Thiệu

RESTful API quản lý danh sách bài hát (Song Management), xây dựng bằng:

| Thành phần | Công nghệ |
|---|---|
| Web Framework | FastAPI 0.100 (async) |
| ORM | SQLModel 0.0.8 (SQLAlchemy async) |
| Database | PostgreSQL 16-alpine |
| DB Driver | asyncpg 0.29.0 |
| Migration | Alembic 1.11.1 |
| Container | Docker + Docker Compose |

**API Endpoints:**

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/ping` | Healthcheck |
| `GET` | `/songs` | Lấy danh sách bài hát |
| `POST` | `/songs` | Thêm bài hát mới |
| `GET` | `/docs` | Swagger UI |

---

## Yêu Cầu Hệ Thống

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) >= 24.0
- [Git](https://git-scm.com/) >= 2.40
- (Optional) Python 3.12 để chạy test local

---

## Setup & Chạy Local Bằng Docker Compose

### Bước 1 – Clone repository

```bash
git clone <repo-url>
cd python-app-backend
```

### Bước 2 – Tạo file `.env`

```bash
cp .env.example .env
# Mở .env và sửa password nếu cần
```

> ⚠️ **Không dùng ký tự `@`, `!`, `#` trong password** – sẽ gây lỗi parse DATABASE_URL.

### Bước 3 – Build và khởi động

```bash
# Build image (lần đầu ~2-3 phút)
docker compose build --no-cache

# Khởi động tất cả services
docker compose up -d

# Kiểm tra trạng thái (songs_db phải là "healthy")
docker compose ps
```

### Bước 4 – Kiểm tra API

```bash
# Healthcheck
curl http://localhost:8004/ping

# Lấy danh sách bài hát
curl http://localhost:8004/songs

# Thêm bài hát
curl -X POST http://localhost:8004/songs \
  -H "Content-Type: application/json" \
  -d '{"name": "Noi Nay Co Anh", "artist": "Son Tung MTP", "year": 2017}'

# Swagger UI (mở trình duyệt)
# http://localhost:8004/docs
```

### Dừng services

```bash
docker compose down          # Giữ nguyên dữ liệu (volume)
docker compose down -v       # Xóa toàn bộ dữ liệu (volume)
```

---

## Chạy Integration Tests

Tests kết nối với **PostgreSQL thật** (không mock), kiểm tra toàn bộ luồng HTTP → API → DB.

### Cách 1 – Chạy trong Docker (khuyến nghị)

```bash
# Đảm bảo DB đang chạy
docker compose up -d db

# Chạy test suite với coverage report
docker compose --profile test run --rm test
```

### Cách 2 – Chạy trực tiếp trong container web

```bash
# Exec vào container đang chạy
docker compose exec web python -m pytest tests/integration/ \
  -v \
  --tb=short \
  --cov=app \
  --cov-report=term-missing \
  --cov-fail-under=80
```

### Kết quả mong đợi

```
tests/integration/test_songs_api.py::test_ping_returns_pong          PASSED
tests/integration/test_songs_api.py::test_docs_accessible            PASSED
tests/integration/test_songs_api.py::test_get_songs_empty            PASSED
tests/integration/test_songs_api.py::test_get_songs_returns_list     PASSED
tests/integration/test_songs_api.py::test_create_song_success        PASSED
tests/integration/test_songs_api.py::test_create_song_without_year   PASSED
tests/integration/test_songs_api.py::test_create_multiple_songs_...  PASSED
tests/integration/test_songs_api.py::test_create_then_retrieve_song  PASSED

---------- coverage: app ----------
TOTAL  coverage: 85%+

8 passed in Xs
```

---

## Kiểm Tra Bảo Mật Container (Non-Root)

```bash
# Xác nhận process chạy với UID 10001 (appuser)
docker compose exec web id
# uid=10001(appuser) gid=10001(appgroup)

docker compose exec web whoami
# appuser
```

---

## Kiểm Tra Data Persistence

```bash
# 1. Tạo dữ liệu
curl -X POST http://localhost:8004/songs \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Persistence", "artist": "DevOps Team", "year": 2024}'

# 2. Restart containers (KHÔNG xóa volume)
docker compose restart

# 3. Chờ DB healthy (~15s), kiểm tra dữ liệu vẫn còn
sleep 15 && curl http://localhost:8004/songs
# → Dữ liệu "Test Persistence" vẫn còn → Named Volume hoạt động ✅
```

---

## Cấu Trúc Dự Án

```
python-app-backend/
├── .env.example              # Template biến môi trường
├── .gitignore
├── docker-compose.yml        # Orchestration: web + db + test
├── LICENSE
├── README.md
└── project/
    ├── .dockerignore
    ├── Dockerfile            # Multi-stage, non-root UID 10001
    ├── alembic.ini
    ├── requirements.txt
    ├── pytest.ini
    ├── app/
    │   ├── __init__.py
    │   ├── db.py             # Database engine & session
    │   ├── main.py           # FastAPI routes + lifespan
    │   └── models.py         # SQLModel: Song, SongCreate
    ├── migrations/
    │   └── versions/         # Alembic migration files
    └── tests/
        └── integration/
            └── test_songs_api.py  # Integration tests (pytest + httpx)
```

---

## Git Workflow

```
main (protected)
  └── feature/phase1-docker   ← Thành viên 1: Infrastructure & Docker
  └── feature/phase1-backend  ← Thành viên 2: Backend & Unit Tests
```

### Quy tắc commit message (Conventional Commits)

```
feat(scope):   tính năng mới
fix(scope):    sửa lỗi
docs(scope):   thay đổi tài liệu
refactor:      cải thiện code không thêm feature
test:          thêm hoặc sửa test
chore:         cấu hình, build scripts
```

### Tạo Pull Request

1. Push nhánh feature lên remote
2. Tạo PR vào `main` trên GitHub
3. PR description ghi rõ: thay đổi, test đã chạy, checklist nghiệm thu
4. Review chéo giữa 2 thành viên trước khi merge
5. Sau khi merge Phase 1: `git tag v1.0.0-phase1`

---

## Nguồn Gốc & Giấy Phép

Dự án này được phát triển dựa trên template mã nguồn mở:

| Thành phần | Nguồn | Giấy phép |
|---|---|---|
| FastAPI framework | [tiangolo/fastapi](https://github.com/tiangolo/fastapi) | MIT |
| SQLModel ORM | [tiangolo/sqlmodel](https://github.com/tiangolo/sqlmodel) | MIT |
| asyncpg driver | [MagicStack/asyncpg](https://github.com/MagicStack/asyncpg) | Apache 2.0 |
| Alembic migration | [sqlalchemy/alembic](https://github.com/sqlalchemy/alembic) | MIT |
| Base template | [testdrivenio/fastapi-sqlmodel-alembic](https://github.com/testdrivenio/fastapi-sqlmodel-alembic) | MIT |

Toàn bộ code trong repository này được phân phối theo **[Giấy phép MIT](LICENSE)**.
