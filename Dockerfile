FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
WORKDIR /app

# Node runtime for the Codex and Claude CLIs, copied from the official image (same glibc base).
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g --no-fund --no-audit @openai/codex@0.153.2 @anthropic-ai/claude-code \
    && npm cache clean --force \
    && codex --version && claude --version

COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist ./static

ENV PATH="/app/.venv/bin:$PATH" \
    TARTIB_DB_PATH=/data/tartib.db \
    TARTIB_STATIC_DIR=/app/static \
    CODEX_HOME=/root/.codex
VOLUME /data
EXPOSE 8000
# --forwarded-allow-ips is what makes --proxy-headers do anything here. On its own that flag
# trusts X-Forwarded-Proto only from 127.0.0.1, and behind a reverse proxy the peer is the
# container network, so the app saw "http", and the session cookie went out without Secure on a
# site served over HTTPS. "*" is safe in this shape and only this shape: nothing reaches the
# port except the proxy in front of it, so the header cannot be set by anyone untrusted.
CMD ["uvicorn", "--factory", "tartib.main:create_app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
