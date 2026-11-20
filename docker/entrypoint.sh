#!/bin/sh
set -eu

# Permite `docker compose run --rm app <comando>` sin arrancar el servidor.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# El esquema lo gobierna Alembic, nunca create_all en producción.
python -m scripts.migrate

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${APP_INTERNAL_PORT:-8050}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers
