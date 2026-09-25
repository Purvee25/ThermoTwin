# syntax=docker/dockerfile:1.7
# ThermoTwin API: build deps with uv, train the forecaster at build time, run as non-root.

FROM ghcr.io/astral-sh/uv:0.11.7-python3.12-trixie-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM build AS train
COPY data/weather ./data/weather
RUN /app/.venv/bin/python -m thermotwin.forecast --patients 200 --seed 7 --save-model

FROM python:3.12-slim-trixie AS runtime
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=build /app/.venv ./.venv
COPY --from=train /app/models/forecast.joblib ./models/forecast.joblib
COPY data/weather ./data/weather
COPY reports/personal_validation.csv ./reports/personal_validation.csv
USER app

# numba (via pythermalcomfort) caches compiled code; site-packages is read-only for app.
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 NUMBA_CACHE_DIR=/tmp/numba-cache
EXPOSE 8010
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=4)"
CMD ["uvicorn", "thermotwin.api.main:app", "--host", "0.0.0.0", "--port", "8010"]
