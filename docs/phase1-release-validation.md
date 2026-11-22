# Kết quả kiểm thử release hardening Phase 1

Ngày 22/11/2026. Kiểm thử trên working tree của `chore/phase1-fix`, base commit `66a2760e2199c80b0fc6400d705df96adf75752e`. Các thay đổi hardening đang chờ review trước commit.

## Kết quả

| Kiểm tra | Kết quả thực tế |
| --- | --- |
| Cài mới dependencies | Python 3.12.10 trên Windows cài thành công `project/requirements-test.txt` vào virtualenv mới. `pip check` báo `No broken requirements found`. |
| Unit tests trên host | `52 passed in 2.71s`. Coverage `app` `100.00%` gồm 126 câu lệnh và 10 nhánh. |
| Cấu hình và build Compose | Compose v2.40.3-desktop.1, Docker Engine 29.0.1. `config --quiet` pass. Build `--no-cache web migrate test` thành công. |
| Migration tự động | PostgreSQL 16.16 mới khởi tạo. `db` healthy, `migrate` chạy `alembic upgrade head` và thoát `0`, sau đó `web` khởi động. `alembic_version` trong PostgreSQL là `750af730f01c`. |
| Smoke test HTTP | Liveness và readiness trả `200` khi DB hoạt động. CRUD trả `201/200/204`, và GET sau DELETE trả `404`. Sau khi dừng DB tạm, liveness vẫn `200` và readiness trả `503` với `{"detail":"Database unavailable"}`. |
| Toàn bộ test trong Compose | Python 3.12.16. `63 passed in 3.84s`, gồm 42 unit test API, 10 test guard và 11 integration tests trên PostgreSQL riêng. Coverage `app` `100.00%` gồm cả nhánh, ngưỡng `80%`. |
| Cô lập dữ liệu test | Config xác nhận runner ở mạng `test_db` nội bộ và môi trường mặc định của runner không nhận `DATABASE_URL`. Bản ghi sentinel trên DB ứng dụng tạm vẫn giữ nguyên sau suite và ba ca thử guard. |
| Runtime image | Python 3.12.16, UID/GID `10001`. Kiểm tra trong container thấy `app/`, `migrations/`, `alembic.ini`. Vắng thư mục `tests/`, file `requirements-test.txt` và các module `pytest`, `pytest_asyncio`, `pytest_cov`, `httpx2`, `httpx`, `psycopg2`. `pip check` pass, có cảnh báo cache pip của user runtime không ghi được. |

Ba ca thử guard được chạy với integration test thật. Khi chỉ có `DATABASE_URL`, collection thoát `2` vì thiếu `TEST_DATABASE_URL`. Khi `TEST_DATABASE_URL` dùng DSN của ứng dụng tạm, collection thoát `2` vì sai đích. Khi DSN trỏ tới PostgreSQL tạm khác có cùng tên DB và role test nhưng thiếu `cluster_name`, kết nối bị chặn trước khi tạo bảng và Pytest thoát `1`. Truy vấn kiểm tra xác nhận PostgreSQL trỏ nhầm vẫn chưa có bảng `song`.

## Phạm vi kiểm thử

Compose regression dùng project `phase1hardeningreg66a`, HTTP loopback và PostgreSQL `tmpfs`. Dữ liệu dùng là dữ liệu tổng hợp. Kiểm tra persistence đo khả năng giữ bản ghi ứng dụng qua lần chạy test. Kịch bản restart trên named volume có sẵn nằm ngoài lần chạy này. Container và mạng regression đã được dọn bằng `docker compose down`.

Image IDs (`docker image inspect`) của lần build:

| Image | ID |
| --- | --- |
| `web` | `sha256:3d6d83f5038e03d0664fe83a59ae9331f998483dc46279ac0ba4a6b7af5aa928` |
| `migrate` | `sha256:b4561acc5e29887120fbf95d3b3c1cea82791927848020b35fb984ebece0d60d` |
| `test` | `sha256:4103fde3c8c3cbf5c53157d0921cd26f4e10f4e09d404b4ebbf4d47e36dcb2e5` |

### Named Volume Persistence — PASS

- Environment: Docker Compose project riêng với PostgreSQL named volume.
- Test: Tạo bản ghi qua `POST /songs`.
- Thực hiện `docker compose down` (không dùng `-v`), sau đó `docker compose up -d`.
- Kết quả: Container PostgreSQL được tạo lại thành công.
- `GET /songs/{id}` trả về đúng bản ghi đã tạo.
- Truy vấn SQL trực tiếp xác nhận dữ liệu vẫn tồn tại.
- Kết luận: **PASS — PostgreSQL duy trì dữ liệu qua quá trình tái tạo container nhờ Docker named volume.**