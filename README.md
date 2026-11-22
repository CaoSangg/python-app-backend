# Song Management API

API FastAPI quản lý bài hát, dùng Python 3.12 và PostgreSQL 16. Xem [tài liệu API](docs/api.md) để biết payload, mã lỗi và ví dụ.

## Chạy bằng Docker Compose

Sử dụng Docker Engine hoặc Docker Desktop với Docker Compose v2. Từ thư mục gốc repository, tạo `.env` từ mẫu nếu chưa có:

```sh
cp .env.example .env
docker compose up -d --build
docker compose ps -a
```

Trên PowerShell, dùng `Copy-Item .env.example .env`. Đổi mật khẩu mẫu trước khi chạy. Cập nhật `DATABASE_URL` cùng giá trị với `POSTGRES_USER`, `POSTGRES_PASSWORD` và `POSTGRES_DB`. Nếu `POSTGRES_PASSWORD` chứa ký tự dành riêng của URL, mã hóa phần mật khẩu trong DSN. Giữ cấu hình database ứng dụng đang dùng khi cập nhật `.env` cũ. Bổ sung cấu hình test từ `.env.example` nếu cần chạy profile `test`.

Compose đợi `db` healthy, chạy `migrate` với `alembic upgrade head`, rồi khởi động `web` khi migration thoát mã `0`. PostgreSQL ứng dụng lưu dữ liệu trong named volume `postgres_data`. `docker compose down` dừng stack và giữ volume. Dùng cùng tên Compose project để tái sử dụng volume hiện có.

Web mặc định ở `http://localhost:8004`. Có thể đổi cổng host bằng `APP_HOST_PORT`. Compose chạy code đóng gói trong image, vì vậy dùng `docker compose up -d --build` sau khi thay đổi code. Runtime dùng UID/GID `10001`. Có thể xác nhận bằng `docker compose exec web id`.

| Method | Endpoint | Kết quả |
| --- | --- | --- |
| `POST` | `/songs` | Tạo bài hát, HTTP `201`. |
| `GET` | `/songs` | Liệt kê bài hát, HTTP `200`. |
| `GET` | `/songs/{song_id}` | Đọc bài hát, HTTP `200` hoặc `404`. |
| `PUT` | `/songs/{song_id}` | Thay thế bài hát, HTTP `200` hoặc `404`. |
| `DELETE` | `/songs/{song_id}` | Xóa bài hát, HTTP `204` hoặc `404`. |
| `GET` | `/ping` | Kiểm tra đơn giản, HTTP `200`. |
| `GET` | `/health/live` | Liveness, HTTP `200`, không truy vấn DB. |
| `GET` | `/health/ready` | Chạy `SELECT 1`, HTTP `200` hoặc `503`. |
| `GET` | `/docs`, `/openapi.json` | Swagger UI và OpenAPI JSON. |

## Dependencies

`project/requirements.txt` ghim FastAPI `0.135.1`, SQLModel `0.0.41`, SQLAlchemy `2.0.58`, asyncpg `0.31.0`, Alembic `1.20.1` và Uvicorn `0.22.0`. `project/requirements-test.txt` include dependencies production và thêm HTTPX2, Pytest, pytest-asyncio và pytest-cov. Docker target `runtime` đóng gói API và migrations. Target `test` cài bộ kiểm thử riêng.

## Chạy kiểm thử

Chạy toàn bộ unit tests và integration tests từ thư mục gốc:

```sh
docker compose --profile test run --rm --build test
```

Đặt `POSTGRES_TEST_PASSWORD` và cập nhật cùng mật khẩu đã mã hóa URL trong `TEST_DATABASE_URL`. Compose chạy `db_test` trên mạng riêng cùng test runner. `db_test` dùng bộ nhớ tạm và role `songs_test_runner` trên database `songs_test_db`. Ứng dụng và runner dùng cấu hình kết nối riêng. Trước khi cấp một kết nối cho fixture hoặc API test, guard kiểm tra database, role và `cluster_name=song_management_integration` do PostgreSQL trả về. Integration tests yêu cầu `TEST_DATABASE_URL` và từ chối DSN có tham số ghi đè kết nối. Fixture được phép tạo bảng, xóa dữ liệu và dọn schema trên DB test này. Chạy từng test runner một lần trên mỗi Compose project vì fixture dùng chung bảng `song`.

Để chạy unit tests trên host với Python 3.12, tạo và kích hoạt virtualenv, sau đó chạy:

```sh
cd project
python -m pip install -r requirements-test.txt
python -m pytest tests/test_api.py tests/test_database_isolation.py --cov=app --cov-branch --cov-fail-under=80
```

## Nguồn và giấy phép

Dự án dựa trên template FastAPI, SQLModel và Alembic của TestDriven.io. [Repository upstream](https://github.com/testdrivenio/fastapi-sqlmodel-alembic) · [Giấy phép MIT](LICENSE)
