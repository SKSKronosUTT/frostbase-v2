FROM python:3.12.8-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --prefix=/install --require-hashes -r requirements.lock


FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=optional
COPY frontend/ ./
RUN npm run build


FROM python:3.12.8-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app/backend

COPY --from=builder /install /usr/local
COPY --chown=app:app backend/ /app/backend/
COPY --from=frontend-builder --chown=app:app /app/frontend/build/ /app/frontend/build/
COPY --chown=app:app frontend/assets/logo-160.png /app/frontend/assets/logo-160.png
COPY --chown=app:app frontend/assets/favicon-32.png /app/frontend/assets/favicon-32.png
COPY --chown=app:app frontend/assets/apple-touch-icon.png /app/frontend/assets/apple-touch-icon.png
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

USER app
EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8050/health/ready', timeout=3).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
