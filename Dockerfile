FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist ./static
ENV PATH="/app/.venv/bin:$PATH" TARTIB_DB_PATH=/data/tartib.db TARTIB_STATIC_DIR=/app/static
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "--factory", "tartib.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
