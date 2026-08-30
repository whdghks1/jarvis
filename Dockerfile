FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system jarvis && adduser --system --ingroup jarvis jarvis

COPY requirements.production.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.production.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY releases ./releases

RUN chown -R jarvis:jarvis /app
USER jarvis

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
