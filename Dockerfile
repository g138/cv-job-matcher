FROM python:3.12-slim

# System deps (pymupdf needs libmupdf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy dependency files first (layer caching)
COPY pyproject.toml uv.lock* ./

# Install deps (no dev extras)
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/
COPY static/ ./static/
COPY knowledge/ ./knowledge/

# Create output dir
RUN mkdir -p output

# Expose port
EXPOSE 8000

# Run with Gunicorn + Uvicorn workers
# Render injects $PORT at runtime; default 8000 for local dev
CMD ["sh", "-c", "uv run gunicorn cv_job_matching_system.api:app \
     -k uvicorn.workers.UvicornWorker \
     -w 2 \
     -b 0.0.0.0:${PORT:-8000} \
     --timeout 600 \
     --graceful-timeout 30"]
