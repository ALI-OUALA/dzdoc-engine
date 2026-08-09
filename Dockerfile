FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra service --extra pdf --extra s3
RUN useradd --create-home --uid 10001 dzdoc && mkdir -p /data && chown -R dzdoc:dzdoc /app /data
USER 10001
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 DZDOC_OBJECT_ROOT=/data/objects
EXPOSE 8000
ENTRYPOINT ["dzdoc-api"]
