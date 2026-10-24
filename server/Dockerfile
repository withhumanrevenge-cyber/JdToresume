# The API as a container image (the deploy target is AWS ECS Fargate, ARCHITECTURE §14). Built from the repo root:
#   docker build -f server/Dockerfile -t tailor-api .
#   docker run -p 8000:8000 -e DATABASE_URL=... -e GROQ_API_KEY=... tailor-api
# Migrations run as a separate one-off task with the same image: python -m alembic upgrade head

FROM python:3.14-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /usr/local/bin/uv

# ENVIRONMENT=production fails closed: the app refuses to start with dev sign-in tokens, so a deploy must set
# AUTH_MODE=jwks, AUTH_JWKS_URL and AUTH_ISSUER (app/core/config.py). Production also turns on JSON logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    ENVIRONMENT=production

WORKDIR /app

# Dependencies first (cached until the lockfile changes), then the code.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY server ./server
COPY templates ./templates
COPY evals ./evals
RUN uv sync --frozen --no-dev

# Run as an unprivileged user.
RUN useradd --system --uid 10001 --no-create-home tailor && chown -R tailor /app
USER tailor

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
