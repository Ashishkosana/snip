FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

EXPOSE 8000

ENV SNIP_DATABASE_URL=sqlite:////data/snip.db
VOLUME ["/data"]

CMD ["uvicorn", "snip.app:app", "--host", "0.0.0.0", "--port", "8000"]
