FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Install all Python dependencies
RUN uv pip install --system --no-cache \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "beanie>=1.26.0" \
    "motor>=3.5.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.3.0" \
    "python-multipart>=0.0.9" \
    "aiofiles>=24.1.0" \
    "cos-python-sdk-v5>=1.9.30" \
    "celery[redis]>=5.4.0" \
    "redis>=5.0.0" \
    "openai>=1.40.0" \
    "instructor>=1.4.0" \
    "volcengine-python-sdk[ark]>=3.0.0" \
    "httpx>=0.27.0" \
    "sse-starlette>=2.1.0" \
    "python-dotenv>=1.0.0"

# Copy source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
