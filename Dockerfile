# ─── AECO Server ───
FROM python:3.11-slim AS backend

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir . && pip install --no-cache-dir gunicorn

# App code
COPY aeco/ aeco/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/

# Create workspace and logs dirs
RUN mkdir -p workspace logs

EXPOSE 8100

# Run with uvicorn (gunicorn for production)
CMD ["uvicorn", "aeco.main:app", "--host", "0.0.0.0", "--port", "8100"]

# ─── Dashboard (build stage) ───
FROM node:20-slim AS dashboard-build

WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci --production=false
COPY dashboard/ .
RUN npm run build

# ─── Final image: server + static dashboard ───
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir . && pip install --no-cache-dir gunicorn

COPY aeco/ aeco/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/

# Copy built dashboard
COPY --from=dashboard-build /app/dashboard/dist dashboard/dist/

RUN mkdir -p workspace logs

EXPOSE 8100

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8100/api/health || exit 1

CMD ["uvicorn", "aeco.main:app", "--host", "0.0.0.0", "--port", "8100"]
