# P2-00 — Backend release baseline

| Mục | Kết quả |
| --- | --- |
| Repository | [CaoSangg/python-app-backend](https://github.com/CaoSangg/python-app-backend) |
| Checkout | `feature/phase2-app-preparation`, working tree sạch trước khi làm. Nhánh chưa có upstream. |
| Source của image | `91df667ec1ad8e877b5a1cab51f1025a3891e515`, trùng local `main`, `origin/main` và remote `refs/heads/main` tại thời điểm đối chiếu. |
| Release Hardening | PR #3 đã merge vào `main` tại `901fe18`. `c2a3b97` là ancestor của baseline. Diff từ merge PR #3 tới baseline rỗng cho `project/`, `docker-compose.yml` và `.env.example`. [PR #3](https://github.com/CaoSangg/python-app-backend/pull/3) |
| Tag | `v1.0.0-phase1` chưa thấy ở Git local hoặc `git ls-remote`. Dùng SHA đã xác minh làm baseline. |
| Stack ghim | Python 3.12, FastAPI 0.135.1, SQLModel 0.0.41, SQLAlchemy 2.0.58, asyncpg 0.31.0, Alembic 1.20.1 và Uvicorn 0.22.0. |
| Contract | CRUD `/songs`, liveness độc lập DB và readiness `SELECT 1` với `200/503`. [API docs](../api.md) |

## Files changed

`docs/phase2/00-baseline.md` ghi baseline và bằng chứng tại SHA đã kiểm tra.

## Kết quả kiểm thử

| Kiểm tra mới tại SHA `91df667` | Kết quả |
| --- | --- |
| `git ls-remote origin refs/heads/main refs/heads/feature/phase2-app-preparation 'refs/tags/v1.0.0-phase1*'` | Trả SHA `91df667…` cho `main`. Chưa thấy nhánh preparation hoặc tag trên remote. |
| `python -m pip check` | PASS trong virtualenv Python 3.12.10. |
| `python -m pytest tests/test_api.py tests/test_database_isolation.py -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80` từ `project/` | **52 passed**, coverage `app` **100%** gồm nhánh. |
| `docker compose --profile test run --rm --build -T test` với project riêng và override tạm | **63 passed** trên Python 3.12.16 gồm 42 unit API, 10 guard và 11 integration tests, coverage `app` **100%** gồm nhánh. Config xác nhận runner chỉ nhận `TEST_DATABASE_URL`, dùng mạng test nội bộ và `db_test` theo guard hiện hành. |
| `python -m alembic heads` và `python -m alembic upgrade head --sql` từ `project/` | Một head `750af730f01c`, sinh SQL PostgreSQL offline thành công. |
| `docker compose up -d --no-build --wait web` với runtime image theo SHA | DB PostgreSQL 16.16 mới trên `tmpfs`, service `migrate` exit `0`, revision `750af730f01c`, có `public.song`. `python -m alembic check` trong runtime báo schema khớp model. |

Regression dùng cấu hình minh họa và Compose project `phase2tv2offline91df`. Endpoint local chỉ mở trên loopback. Log kiểm tra named-volume trong [báo cáo Phase 1](../phase1-release-validation.md) là bằng chứng lịch sử. Lượt này giữ cùng DB tạm qua tái tạo container web để kiểm tra workload.

## Dependency còn thiếu

Tag release cần được nhóm chốt nếu quy trình phát hành yêu cầu. SHA hiện có đủ để kiểm tra và chuẩn bị local.

## Trạng thái

**PASS** cho baseline theo SHA, regression và bằng chứng local. Tag được ghi riêng ở bảng Git.
