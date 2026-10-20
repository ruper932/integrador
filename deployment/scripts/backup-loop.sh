#!/bin/sh
# Genera un respaldo comprimido de PostgreSQL cada BACKUP_INTERVAL_SECONDS
# y elimina los respaldos con más de BACKUP_RETENTION_DAYS días.
set -eu
mkdir -p /backups
while true; do
  file="/backups/atrapanieblas_$(date +%Y%m%d_%H%M%S).dump"
  if pg_dump --format=custom --file="$file.tmp"; then
    mv "$file.tmp" "$file"
    echo "$(date -Iseconds) respaldo creado: $file"
  else
    rm -f "$file.tmp"
    echo "$(date -Iseconds) ERROR al crear el respaldo" >&2
  fi
  find /backups -name 'atrapanieblas_*.dump' -mtime +"${BACKUP_RETENTION_DAYS:-30}" -delete
  sleep "${BACKUP_INTERVAL_SECONDS:-86400}"
done
