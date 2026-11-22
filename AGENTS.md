# Hướng dẫn làm việc với Song Management API

## Phạm vi và nguồn thông tin

- Áp dụng cho repository `python-app-backend`. Đọc source, cấu hình và tests trên branch hiện tại trước khi thay đổi. Dùng `README.md` và `docs/api.md` để tra lệnh và contract. Dùng `PHASE2.md` ở thư mục gốc workspace để xác định phạm vi Phase 2 và phân công. Nếu thiếu tài liệu hoặc source khác tài liệu, ghi rõ chỗ chưa xác minh để cả nhóm review.
- Kiểm tra `git status --short --branch` trước khi làm. Giữ các thay đổi có sẵn của người dùng. Chỉ sửa file cần cho yêu cầu. Chỉ tạo branch, commit, push, merge hoặc tag khi được yêu cầu.
- TV2 phụ trách backend, baseline release image và bằng chứng workload. TV1 phụ trách Terraform, AWS, Ansible và nền tảng Harbor/K3s. TV2 phối hợp kiểm tra outputs, network/SG, registry trust và kết nối RDS. Việc chuẩn bị workload không cấp quyền thay đổi AWS, cluster hoặc registry.

## FastAPI, PostgreSQL và dependencies

- Stack hiện tại là Python 3.12, FastAPI, SQLModel, SQLAlchemy async, asyncpg và PostgreSQL 16. Entrypoint là `app.main:app` từ thư mục `project`. Giữ async engine/session lifecycle trong `project/app/db.py` và tái sử dụng `get_session` cho CRUD. Cấu hình kết nối qua `DATABASE_URL` dạng `postgresql+asyncpg://…`.
- Giữ contract trong `project/app/main.py`, `project/app/models.py` và `docs/api.md`. CRUD dùng `/songs` và `/songs/{song_id}`. Tạo trả `201`, đọc và cập nhật trả `200`, xóa trả `204` với body rỗng, ID hợp lệ không tồn tại trả `404` và validation trả `422`. `PUT` thay thế toàn bộ bản ghi và lưu `year=null` nếu bỏ qua trường này. Giữ `/ping`, `/docs` và `/openapi.json`.
- `/health/live` trả `200` và không kết nối DB. `/health/ready` kiểm tra `SELECT 1` với thời gian chờ hai giây, trả `200` hoặc `503`. Giữ thông báo lỗi và logs an toàn. Không ghi credentials, DSN, query parameters nhạy cảm hoặc stack trace chứa bí mật vào response, test log hoặc tài liệu bàn giao.
- Ghim dependencies runtime trong `project/requirements.txt`. `project/requirements-test.txt` include file runtime và chứa httpx, Pytest, pytest-asyncio và pytest-cov. Thay đổi package có chủ đích và tránh pin mâu thuẫn giữa hai file. Dùng `.env.example` với giá trị minh họa. Cấp mật khẩu và DSN thực qua cấu hình môi trường bên ngoài Git.

## Alembic

- Alembic quản lý schema ứng dụng. `project/alembic.ini` trỏ tới `project/migrations`, online migrations đọc `DATABASE_URL`. Lifespan của FastAPI chỉ quản lý kết nối. Giới hạn `SQLModel.metadata.create_all()` và `drop_all()` ở fixture đã xác minh đích test.
- Head Phase 1 là `750af730f01c`, hợp nhất hai lịch sử upstream. Giữ ID và lịch sử revision đã phát hành. Khi sửa schema, thêm revision tiếp nối head và kiểm tra cả DB trống lẫn đường nâng cấp có dữ liệu. Downgrade qua revision hợp nhất bị chặn. Chỉ chạy downgrade hoặc thao tác phá hủy dữ liệu khi có yêu cầu rõ và đã xác minh đích.
- Từ `project/`, dùng `python -m alembic heads` để xem đồ thị head và `python -m alembic upgrade head --sql` để xem SQL offline. Trên PostgreSQL thử nghiệm đã xác minh, dùng `python -m alembic upgrade head`, `python -m alembic current` và `python -m alembic check` để kiểm tra revision và schema. SQL offline không thay cho bằng chứng chạy migration trên PostgreSQL.

## Docker và Pytest

- Build từ context `project/` với Dockerfile multi-stage. `runtime` đóng gói app, migrations và dependencies production, chạy UID/GID `10001:10001` và cổng `8000`. `test` cài dependencies kiểm thử riêng. Giữ test files, test packages và secrets ngoài runtime. Kiểm tra image phát hành khi sửa Dockerfile hoặc dependencies.
- Compose chờ `db` healthy, chạy `migrate` bằng `alembic upgrade head` và chỉ khởi động `web` sau khi migration thành công. Cổng host mặc định là `8004`, cấu hình qua `APP_HOST_PORT`. Named volume `postgres_data` giữ dữ liệu ứng dụng cùng Compose project. Khi thử build hoặc migration từ DB trống, dùng Compose project riêng và giữ các volume có dữ liệu.
- Trước khi chạy kiểm thử, kiểm tra lại đường dẫn file test thực tế trong `project/tests/`, cấu hình service/profile trong `docker-compose.yml` và biến môi trường trên source hiện tại; tuyệt đối không sử dụng database ứng dụng (`DATABASE_URL`, volume `postgres_data` hoặc DB môi trường thật) cho integration tests.
- Unit tests mock engine/session và chạy độc lập với PostgreSQL. Sau khi xác minh đường dẫn test từ `project/`, cài bộ test vào virtualenv Python 3.12 rồi chạy:

  ```sh
  python -m pip install -r requirements-test.txt
  python -m pytest tests/test_api.py tests/test_database_isolation.py --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80
  ```

- Sau khi xác minh cấu hình profile `test` và biến môi trường kiểm thử trong `.env` trên source hiện tại, chạy toàn bộ unit và integration tests từ gốc repo:

  ```sh
  docker compose --profile test run --rm --build test
  ```

- Integration tests yêu cầu `TEST_DATABASE_URL`, không fallback sang `DATABASE_URL` và tuyệt đối không dùng database ứng dụng. Compose đặt runner và `db_test` trên mạng nội bộ `test_db`. `db_test` dùng database `songs_test_db`, role `songs_test_runner` và `cluster_name=song_management_integration`. Giữ guard kiểm tra DSN và danh tính thật do PostgreSQL trả về trước khi cấp kết nối cho fixture hoặc app test. `DELETE`, `create_all()` và `drop_all()` chỉ chạy trên đích test đã xác minh. Chạy một runner mỗi Compose project vì suite dùng chung bảng `song`.
- Giữ ngưỡng coverage `app` ≥80%. Khi bàn giao thay đổi, ghi SHA, lệnh, số test, coverage và kết quả thực tế. Phân biệt test đã chạy, bằng chứng lịch sử và hạng mục chưa kiểm chứng. `docs/phase1-release-validation.md` lưu kết quả 63 test của lần regression Phase 1. Dùng Git history để xác định trạng thái merge và kiểm tra lại trên SHA cần bàn giao.

## Kubernetes workload Phase 2

Áp dụng khi có yêu cầu làm workload. Theo `PHASE2.md` §2 và §4 (P2-00, P2-07 đến P2-11), TV2 chốt source SHA, kiểm tra image runtime non-root và kiến trúc image, hỗ trợ push thủ công lên Harbor HTTPS, ghi tag theo SHA và digest, rồi kiểm tra Worker pull được image qua CA tin cậy. TV2 phụ trách manifests tối thiểu trong `k8s-gitops-manifests` hoặc vị trí demo hai bên đã chốt, kiểm thử FastAPI với RDS và báo cáo bằng chứng ứng dụng.

- Chuẩn bị Namespace, ConfigMap khi cần, tham chiếu Secret runtime, Migration Job, Deployment, ClusterIP Service và Ingress. Giữ UID/GID runtime `10001:10001` và cổng ứng dụng `8000`. Cấp `DATABASE_URL` và `imagePullSecrets` lúc triển khai theo phương án đã duyệt. Không commit plaintext Secret, mật khẩu, DSN, registry token, private key hoặc kubeconfig. Base64 không bảo vệ Secret trong Git.
- Kiểm tra RDS private sẵn sàng và đường TCP `5432` chỉ từ Worker SG theo thiết kế. Đặt Job và API Pods trên Worker bằng selector/affinity phù hợp với labels thực tế. Job dùng cùng image digest với ứng dụng, chạy `alembic upgrade head` tới cùng cơ sở dữ liệu, dùng role migrator riêng nếu khả thi. Chỉ rollout sau khi Job thành công. Khi Job lỗi, dừng rollout và kiểm tra log đã loại thông tin nhạy cảm.
- Liveness dùng `/health/live`, readiness dùng `/health/ready`. Readiness kiểm tra kết nối DB. Job thành công và schema đúng là bằng chứng migration riêng. Qua Ingress, kiểm tra probes và CRUD, xác minh bản ghi vẫn còn sau khi tạo lại API Pod. Chỉ mô phỏng mất DB trong môi trường kiểm thử có kiểm soát. Ghi SHA, digest, kết quả pull, Job/revision, rollout, HTTP status và persistence.
- Phase 2 dùng triển khai thủ công sau khi nhóm duyệt các phụ thuộc. GitHub Actions, chất lượng CI tự động, Argo CD, Kustomize đa môi trường và Sealed Secrets thuộc Phase 3.
- **Báo cáo bắt buộc sau mỗi work package (`P2-xx`):** Ngay sau khi thực hiện xong hoặc dừng xử lý từng work package `P2-xx`, Agent phải tổng hợp báo cáo gồm đầy đủ 4 mục:
  1. **Files changed:** Danh sách file đã thêm/sửa/xóa kèm tóm tắt nội dung thay đổi (ghi `Không có` nếu chỉ kiểm tra).
  2. **Kết quả kiểm thử:** Lệnh đã thực thi, kết quả thực tế (HTTP status, log, số test, coverage nếu có); tách bạch phần đã chạy trên source hiện tại với bằng chứng lịch sử.
  3. **Dependency còn thiếu:** Các hạng mục phụ thuộc chưa sẵn sàng từ TV1, hạ tầng AWS/Harbor/K3s/RDS, secret runtime hoặc tài liệu chưa chốt.
  4. **Trạng thái:** Gán nhãn chính xác một trong bốn trạng thái `PASS`, `PARTIAL`, `BLOCKED`, hoặc `NOT VERIFIED` kèm lý do ngắn gọn.