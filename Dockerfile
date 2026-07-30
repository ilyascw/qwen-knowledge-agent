# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS runtime

ARG QWEN_CODE_VERSION=0.13.1
ARG UV_VERSION=0.10.6

ENV DEBIAN_FRONTEND=noninteractive \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp/qwen-home \
    AGENT_PROFILE_DIR=/app/agent \
    MEMORY_DB_PATH=/data/memory.db \
    QWEN_RUNTIME_DIR=/data/qwen-runtime \
    QWEN_WORKSPACE_DIR=/data/qwen-workspace

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@qwen-code/qwen-code@${QWEN_CODE_VERSION}" \
    && npm cache clean --force \
    && curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | env UV_INSTALL_DIR=/usr/local/bin sh

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY agent ./agent
RUN uv sync --frozen --no-dev \
    && mkdir -p /data /tmp/qwen-home \
    && chown -R node:node /data /tmp/qwen-home

USER node

VOLUME ["/data"]
ENTRYPOINT ["knowledge-agent"]
