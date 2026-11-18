#!/usr/bin/env bash
#
# Wrapper de respaldo para cron/systemd.
#
# Instalación sugerida:
#   sudo install -d -o root -g frostbase -m 750 /opt/frostbase/deploy/cron
#   sudo install -o root -g frostbase -m 750 deploy/cron/frostbase-backup.sh \
#       /opt/frostbase/deploy/cron/frostbase-backup.sh
#   sudo install -d -o root -g frostbase -m 750 /etc/frostbase
#   sudo install -o root -g frostbase -m 600 deploy/systemd/backup.env.example \
#       /etc/frostbase/backup.env
#   sudo install -o root -g frostbase -m 600 /dev/null /etc/frostbase/backup.pass
#   # Escriba la passphrase de 32+ caracteres en /etc/frostbase/backup.pass
#
# El script no recibe secretos por argumento. La passphrase se lee de un archivo
# con permisos restringidos o de FROSTBASE_BACKUP_PASSPHRASE.
set -euo pipefail

ENV_FILE="${FROSTBASE_ENV_FILE:-/etc/frostbase/backup.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${FROSTBASE_DIR:=/opt/frostbase}"
: "${FROSTBASE_PYTHON:=python3}"
: "${FROSTBASE_DB:=frostbase}"
: "${FROSTBASE_BACKUP_DIR:=/var/backups/frostbase}"
: "${FROSTBASE_RETENTION_DAYS:=30}"
: "${FROSTBASE_KEEP_LAST:=7}"
: "${FROSTBASE_MIRROR_DIR:=}"

if [[ -z "${FROSTBASE_BACKUP_PASSPHRASE_FILE:-}" ]]; then
  echo "ERROR: defina FROSTBASE_BACKUP_PASSPHRASE_FILE en $ENV_FILE" >&2
  exit 2
fi

args=(
  "$FROSTBASE_DIR/backend/scripts/db_backup.py"
  --db "$FROSTBASE_DB"
  --label nightly
  --out-dir "$FROSTBASE_BACKUP_DIR"
  --encrypt
  --passphrase-file "$FROSTBASE_BACKUP_PASSPHRASE_FILE"
  --prune
  --retention-days "$FROSTBASE_RETENTION_DAYS"
  --keep-last "$FROSTBASE_KEEP_LAST"
  --verify
)

if [[ -n "$FROSTBASE_MIRROR_DIR" ]]; then
  args+=(--mirror-dir "$FROSTBASE_MIRROR_DIR")
fi

exec "$FROSTBASE_PYTHON" "${args[@]}"
