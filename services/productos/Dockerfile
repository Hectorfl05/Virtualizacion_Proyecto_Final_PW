# Multi-stage build para microservicio de Productos
# Etapa 1: Builder con uv para sincronización congelada de dependencias
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.15 /uv /bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Sincronizar dependencias en capa cacheable usando uv.lock
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copiar el código fuente y artefactos requeridos
COPY pyproject.toml uv.lock alembic.ini ./
COPY migrations/ ./migrations/
COPY app/ ./app/

# Sincronizar el proyecto
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Etapa 2: Runner final minimalista y seguro
FROM python:3.12-slim AS runner

WORKDIR /app

# Crear usuario de sistema no privilegiado (UID/GID 10001)
RUN groupadd -r -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup -s /sbin/nologin -d /app appuser

# Copiar entorno virtual y aplicación desde la etapa de construcción
COPY --from=builder --chown=appuser:appgroup /app /app

USER appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
