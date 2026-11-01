FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONPATH=/app/api \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

WORKDIR /app

COPY pyproject.toml README.md ./
RUN uv sync --no-install-project --no-cache

COPY api ./api
COPY scripts ./scripts
COPY data ./data

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data /app/logs \
    && chown -R app:app /data /app/logs /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
