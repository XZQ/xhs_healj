FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[postgres]"

EXPOSE 8000

CMD ["uvicorn", "xhs_health.main:app", "--host", "0.0.0.0", "--port", "8000"]

