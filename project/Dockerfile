# =============================================================
# Dockerfile Multi-stage – Song Management API
# Stage 1 (builder): cài dependencies vào venv riêng
# Stage 2 (runtime): copy venv, chạy non-root UID 10001
# =============================================================

# ── Stage 1: builder ─────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Cài build deps (gcc cho compile nếu cần)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Tạo virtualenv riêng để copy sang stage 2 dễ dàng
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt


# ── Test runner: extends the builder venv for this target only ────
FROM builder AS test

COPY requirements-test.txt .
RUN pip install -r requirements-test.txt


# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /usr/src/app

# Copy virtualenv đã build từ stage 1
COPY --from=builder /opt/venv /opt/venv

# Tạo non-root user với UID 10001 (security best practice)
RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appgroup /usr/src/app

# Copy only the API and files needed by Alembic
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup migrations/ ./migrations/
COPY --chown=appuser:appgroup alembic.ini .

# Switch sang non-root user TRƯỚC khi expose/cmd
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
