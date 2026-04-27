FROM python:3.12-slim

# System deps (pymupdf needs libmupdf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy everything needed for the build
COPY pyproject.toml uv.lock* ./
COPY src/ ./src/
COPY static/ ./static/
COPY knowledge/ ./knowledge/

# Install deps (no dev extras)
RUN uv sync --frozen --no-dev

# Create output dir
RUN mkdir -p output

# Expose port
EXPOSE 8000

# Render injects $PORT at runtime; default 8000 for local dev
CMD ["sh", "-c", ".venv/bin/uvicorn cv_job_matching_system.api:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 600"]
