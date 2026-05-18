# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY workers/ ./workers/
COPY .env ./

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN useradd --no-create-home --uid 1001 quama
USER quama

EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
