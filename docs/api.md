# Song Management API

Xem Swagger UI tại `/docs` và OpenAPI JSON tại `/openapi.json`.

## Bài hát

| Method | Endpoint | Thành công | Lỗi theo yêu cầu |
| --- | --- | --- | --- |
| `POST` | `/songs` | `201 Created`, trả về bài hát mới | `422` |
| `GET` | `/songs` | `200 OK`, trả về mảng bài hát theo ID tăng dần. Mảng rỗng là `[]`. | |
| `GET` | `/songs/{song_id}` | `200 OK`, trả về bài hát | `404`, `422` |
| `PUT` | `/songs/{song_id}` | `200 OK`, trả về bài hát sau khi thay thế toàn bộ nội dung | `404`, `422` |
| `DELETE` | `/songs/{song_id}` | `204 No Content`, thân phản hồi rỗng | `404`, `422` |

`song_id` là số nguyên từ 1 đến 2147483647. PostgreSQL cấp ID khi tạo bài hát.

### Request cho POST và PUT

Gửi `Content-Type: application/json`.

```json
{
  "name": "Midnight Fit",
  "artist": "Mogwai",
  "year": 2021
}
```

- `name` và `artist` là chuỗi bắt buộc. API cắt khoảng trắng ở hai đầu và từ chối chuỗi rỗng hoặc chứa ký tự NUL.
- `year` là số nguyên có dấu 32 bit hoặc `null`. API cũng chấp nhận chuỗi số nguyên như `"2021"` để tương thích với ví dụ upstream.
- Cả `POST` và `PUT` lưu `year` là `null` nếu bỏ qua trường này. `PUT` yêu cầu cả `name` và `artist`.

### Response cho POST, GET theo ID và PUT

```json
{
  "id": 1,
  "name": "Midnight Fit",
  "artist": "Mogwai",
  "year": 2021
}
```

`GET /songs` trả về mảng các đối tượng cùng cấu trúc. Lỗi `404` trả về `{"detail":"Song not found"}`. Lỗi `422` trả về mảng lỗi FastAPI trong trường `detail`, gồm vị trí và thông báo lỗi. Khi thiếu `DATABASE_URL`, các thao tác bài hát trả `503` với `{"detail":"Database unavailable"}`. Nếu thao tác PostgreSQL thất bại, API trả `500` với `{"detail":"Database operation failed"}`.

## Health checks

| Method | Endpoint | Response |
| --- | --- | --- |
| `GET` | `/ping` | `200 OK` với `{"ping":"pong!"}` |
| `GET` | `/health/live` | `200 OK` với `{"status":"ok"}`. Endpoint hoạt động độc lập với PostgreSQL. |
| `GET` | `/health/ready` | `200 OK` với `{"status":"ok"}` khi `SELECT 1` thành công. Trả `503 Service Unavailable` với `{"detail":"Database unavailable"}` khi thiếu cấu hình, lỗi kết nối, lỗi truy vấn hoặc hết thời gian chờ. |

Readiness dành tối đa 2 giây cho kiểm tra PostgreSQL. Response lỗi giữ kín connection string và thông tin xác thực.

## PostgreSQL và Alembic

Từ thư mục `project`, cài `requirements.txt` bằng Python 3.12. Cấp `DATABASE_URL` dạng `postgresql+asyncpg://<user>:<password>@<host>:5432/<database>` cho cả API và Alembic. Nếu thông tin xác thực chứa ký tự dành riêng của URL, dùng percent-encoding.

```sh
python -m alembic heads
python -m alembic upgrade head
python -m alembic check
python -m uvicorn app.main:app
```

Chạy migration trước khi đưa CRUD vào phục vụ. Readiness kiểm tra kết nối PostgreSQL. Alembic quản lý schema của bảng `song`.

Head `750af730f01c` hợp nhất hai lịch sử upstream. Upgrade giữ dữ liệu bài hát và chỉ xóa ba index dư từ lịch sử cũ. Downgrade qua revision hợp nhất bị chặn để bảo vệ bảng `song` dùng chung giữa hai lịch sử. Có thể xem SQL PostgreSQL trước khi áp dụng bằng `python -m alembic upgrade head --sql`.

## Unit tests

Từ thư mục `project`:

```sh
python -m pip install -r requirements-test.txt
python -m pytest tests/test_api.py tests/test_database_isolation.py --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80
```

Unit tests mô phỏng engine và session để chạy độc lập với PostgreSQL. Để chạy cả integration tests với DB test riêng, xem [README](../README.md#chạy-kiểm-thử). Nguồn upstream và tác giả được ghi nhận theo giấy phép đi kèm. [TestDriven.io](https://github.com/testdrivenio/fastapi-sqlmodel-alembic) · [LICENSE](../LICENSE)
