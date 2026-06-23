FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY data ./data

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /root/.cache/pip

CMD ["bash", "-lc", "python scripts/run_migrations.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
