# Pit Wall — F1 podium intelligence dashboard.
#   docker build -t pitwall .
#   docker run --rm -p 5173:5173 pitwall
# First start self-builds the feature table + models from the bundled CSVs
# (offline); telemetry-backed tabs fetch on demand and cache in the container.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# dependency layer (cached unless the lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra vision --no-install-project

# project
COPY src ./src
COPY web ./web
COPY data/processed ./data/processed
COPY README.md ./
RUN uv sync --frozen --extra vision

# pre-build features + models into the image so first launch is instant
RUN uv run f1ml setup

EXPOSE 5173
ENV PORT=5173 HOST=0.0.0.0
# invoke the venv directly (no uv at runtime) so it also runs read-only /
# as a non-root user, e.g. on Hugging Face Spaces
CMD ["/app/.venv/bin/python", "-m", "f1_ml.cli", "serve"]
